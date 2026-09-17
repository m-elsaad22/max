#!/usr/bin/env python3
"""Phase 2 — filesystem cleanup + post-body JSON-LD strip + featured-image diversification.

Default mode is a dry run (no deletes, no PUT/POST). Pass --execute after review.

Credentials (.env or environment), any of:
  WP_URL / WP_BASE_URL
  WP_USER / WP_USERNAME
  WP_APP_PASSWORD
  WP_ROOT   absolute path to the WordPress document root ON THE MACHINE THAT
            actually hosts the files (wp-config.php must exist there).

This Cursor workspace is the connector repo, not the live WordPress tree.
Task 1 only works when WP_ROOT points at a real WordPress install.

Never prints the application password.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wp_connect import USER_AGENT, load_dotenv  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://max-art-ae.com"
LOGO_MEDIA_ID = 3362  # site logo — do not recycle as a featured image
JSONLD_RE = re.compile(
    r"""<script\b(?=[^>]*\btype\s*=\s*['"]application/ld\+json['"])[^>]*>.*?</script>"""
    r"""(?:\s*<p>\s*</p>)?""",
    re.IGNORECASE | re.DOTALL,
)
PLUGIN_TARGETS: dict[str, tuple[str, ...]] = {
    "wordpress-seo": ("wordpress-seo",),
    "mpg-multiple-pages-generator": (
        "mpg-multiple-pages-generator",
        "multiple-pages-generator-by-themeisle",
        "multi-pages-generator",
        "multiple-pages-generator",
        "mpg",
    ),
    "weglot": ("weglot",),
}


def env_first(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return default


def config() -> tuple[str, str, str, Path | None]:
    load_dotenv(REPO_ROOT / ".env")
    url = env_first("WP_BASE_URL", "WP_URL", default=DEFAULT_URL).rstrip("/")
    user = env_first("WP_USERNAME", "WP_USER")
    password = env_first("WP_APP_PASSWORD")
    root_raw = env_first("WP_ROOT")
    if not user or not password:
        sys.exit("Missing WP_USER/WP_USERNAME or WP_APP_PASSWORD in .env")
    wp_root = Path(root_raw).expanduser().resolve() if root_raw else None
    return url, user, password, wp_root


def auth_header(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def http(
    url: str,
    user: str,
    password: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 90,
) -> tuple[int, dict[str, str], Any]:
    body = None
    headers = {
        "Authorization": auth_header(user, password),
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last: Exception | None = None
    for attempt in range(5):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                hdrs = {k.lower(): v for k, v in response.headers.items()}
                parsed: Any = None
                if raw:
                    try:
                        parsed = json.loads(raw.decode("utf-8"))
                    except json.JSONDecodeError:
                        parsed = raw.decode("utf-8", errors="replace")
                return response.status, hdrs, parsed
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            hdrs = {k.lower(): v for k, v in exc.headers.items()}
            if exc.code in (404, 405, 409, 422) or (400 <= exc.code < 500 and exc.code != 429):
                try:
                    parsed = json.loads(detail) if detail else None
                except json.JSONDecodeError:
                    parsed = {"raw": detail[:1500]}
                return exc.code, hdrs, parsed
            last = RuntimeError(f"HTTP {exc.code} {method} {url}\n{detail[:1500]}")
            time.sleep(1.4 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.4 * (attempt + 1))
    raise RuntimeError(f"request failed after retries: {last}")


def rest(
    base: str,
    user: str,
    password: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, str], Any]:
    if not path.startswith("/"):
        path = "/" + path
    target = f"{base}{path}" if path.startswith("/wp-json") else f"{base}/wp-json{path}"
    return http(target, user, password, method=method, payload=payload)


def put_or_post_post(
    base: str,
    user: str,
    password: str,
    post_id: int,
    payload: dict[str, Any],
) -> tuple[str, int]:
    path = f"/wp/v2/posts/{post_id}"
    code, _hdrs, _body = rest(base, user, password, path, method="PUT", payload=payload)
    if code in (200, 201):
        return "PUT", code
    if code == 405:
        code2, _h2, _b2 = rest(base, user, password, path, method="POST", payload=payload)
        return "POST", code2
    return "PUT", code


def fetch_pages(
    base: str,
    user: str,
    password: str,
    rest_base: str,
    extra: dict[str, str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        query = {"per_page": "50", "page": str(page), **extra}
        q = urllib.parse.urlencode(query)
        code, hdrs, data = rest(base, user, password, f"/wp/v2/{rest_base}?{q}")
        if code in (400, 404) and page > 1:
            break
        if code != 200:
            raise RuntimeError(f"GET /wp/v2/{rest_base} page {page} HTTP {code}: {data}")
        batch = data if isinstance(data, list) else []
        items.extend(batch)
        total_pages = int(hdrs.get("x-wp-totalpages") or "1")
        print(f"  {rest_base} page {page}/{total_pages} (+{len(batch)})", flush=True)
        if page >= total_pages or len(batch) < 50:
            break
        page += 1
        time.sleep(0.12)
    return items


def looks_like_wordpress(root: Path) -> bool:
    return (root / "wp-config.php").is_file() or (root / "wp-load.php").is_file()


def resolve_plugin_dir(plugins_root: Path, aliases: tuple[str, ...]) -> Path | None:
    for slug in aliases:
        candidate = plugins_root / slug
        if candidate.is_dir():
            return candidate
    return None


def plugin_status(
    base: str, user: str, password: str, file: str
) -> str | None:
    """Return 'active' / 'inactive' when the plugins REST route exists, else None."""
    slug = f"{file}/{file}"
    code, _hdrs, data = rest(base, user, password, f"/wp/v2/plugins/{slug}")
    if code != 200 or not isinstance(data, dict):
        return None
    status = data.get("status")
    return str(status) if status else None


def task1_filesystem(
    wp_root: Path | None,
    execute: bool,
    base: str,
    user: str,
    password: str,
) -> dict[str, Any]:
    report: dict[str, Any] = {"ok": True, "actions": [], "skipped": []}
    if wp_root is None:
        report["ok"] = False
        report["skipped"].append("WP_ROOT is unset — Task 1 requires the live WordPress document root.")
        return report
    if not wp_root.is_dir():
        report["ok"] = False
        report["skipped"].append(f"WP_ROOT does not exist: {wp_root}")
        return report
    if not looks_like_wordpress(wp_root):
        report["ok"] = False
        report["skipped"].append(
            f"WP_ROOT is not a WordPress install (no wp-config.php / wp-load.php): {wp_root}"
        )
        return report

    sitemap = wp_root / "mpg-sitemap-plumbing-services.xml"
    if sitemap.is_file():
        report["actions"].append({"op": "delete_file", "path": str(sitemap), "existed": True})
        if execute:
            sitemap.unlink()
            print(f"deleted {sitemap}")
        else:
            print(f"dry-run would delete {sitemap}")
    else:
        report["skipped"].append(f"sitemap not found (already gone?): {sitemap}")
        print(f"skip missing {sitemap}")

    plugins_root = wp_root / "wp-content" / "plugins"
    if not plugins_root.is_dir():
        report["ok"] = False
        report["skipped"].append(f"plugins directory missing: {plugins_root}")
        return report

    for label, aliases in PLUGIN_TARGETS.items():
        found = resolve_plugin_dir(plugins_root, aliases)
        if found is None:
            report["skipped"].append(f"plugin folder not found for {label} (tried {', '.join(aliases)})")
            print(f"skip missing plugin {label}")
            continue
        status = plugin_status(base, user, password, found.name)
        if status == "active":
            report["ok"] = False
            report["skipped"].append(f"refusing to delete ACTIVE plugin {found.name} ({label})")
            print(f"refuse active plugin {found}")
            continue
        report["actions"].append(
            {
                "op": "rmtree",
                "path": str(found),
                "label": label,
                "existed": True,
                "rest_status": status or "unknown",
            }
        )
        if execute:
            shutil.rmtree(found)
            print(f"deleted plugin tree {found}")
        else:
            print(f"dry-run would rmtree {found}")
    return report


def post_raw_html(post: dict[str, Any]) -> str:
    content = post.get("content") or {}
    if isinstance(content, dict):
        raw = content.get("raw")
        if isinstance(raw, str) and raw.strip():
            return raw
        rendered = content.get("rendered")
        if isinstance(rendered, str):
            return rendered
    return ""


def strip_jsonld(html: str) -> tuple[str, int]:
    cleaned, n = JSONLD_RE.subn("", html)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if html.endswith("\n") and cleaned:
        cleaned += "\n"
    return cleaned, n


def task2_strip_jsonld(
    base: str,
    user: str,
    password: str,
    execute: bool,
    limit: int | None,
) -> dict[str, Any]:
    posts = fetch_pages(
        base,
        user,
        password,
        "posts",
        {"status": "publish", "context": "edit", "_fields": "id,link,status,content,featured_media"},
    )
    if limit is not None:
        posts = posts[:limit]
    changed: list[dict[str, Any]] = []
    skipped = 0
    errors: list[dict[str, Any]] = []
    for post in posts:
        pid = int(post["id"])
        html = post_raw_html(post)
        cleaned, n = strip_jsonld(html)
        if n == 0:
            skipped += 1
            continue
        entry = {"id": pid, "link": post.get("link"), "scripts_removed": n}
        if not execute:
            changed.append(entry)
            continue
        method, code = put_or_post_post(base, user, password, pid, {"content": cleaned})
        entry["http"] = code
        entry["method"] = method
        if code not in (200, 201):
            errors.append(entry)
            print(f"JSON-LD strip FAIL post {pid} HTTP {code}")
        else:
            changed.append(entry)
            print(f"JSON-LD strip {method} {pid} removed={n}")
        time.sleep(0.08)
    print(f"JSON-LD: {len(changed)} with embedded schema, {skipped} clean, {len(errors)} errors")
    return {"scanned": len(posts), "updated": changed, "clean": skipped, "errors": errors}


def task3_diversify_featured(
    base: str,
    user: str,
    password: str,
    execute: bool,
    seed: int,
    limit: int | None,
) -> dict[str, Any]:
    posts = fetch_pages(
        base,
        user,
        password,
        "posts",
        {"status": "publish", "context": "edit", "_fields": "id,link,featured_media"},
    )
    media = fetch_pages(
        base,
        user,
        password,
        "media",
        {"media_type": "image", "per_page": "50", "_fields": "id,mime_type,source_url,media_type"},
    )
    counts = Counter(int(p.get("featured_media") or 0) for p in posts)
    overused_id, overused_n = counts.most_common(1)[0] if counts else (0, 0)
    pool = sorted(
        {
            int(m["id"])
            for m in media
            if str(m.get("mime_type") or "").startswith("image/")
            and int(m["id"]) not in {0, overused_id, LOGO_MEDIA_ID}
        }
    )
    targets = [p for p in posts if int(p.get("featured_media") or 0) == overused_id and overused_id]
    if limit is not None:
        targets = targets[:limit]

    report: dict[str, Any] = {
        "overused_featured_id": overused_id,
        "overused_count": overused_n,
        "media_pool_size": len(pool),
        "assignments": [],
        "errors": [],
        "skipped": [],
    }
    if overused_id == 0 or overused_n < 10:
        report["skipped"].append(
            f"No dominant featured-image footprint (top id={overused_id} count={overused_n})."
        )
        print(report["skipped"][-1])
        return report
    if len(pool) < 3:
        report["skipped"].append(
            f"Media pool too small ({len(pool)}) after excluding overused id {overused_id} and logo {LOGO_MEDIA_ID}."
        )
        print(report["skipped"][-1])
        return report

    rng = random.Random(seed)
    cycle = pool[:]
    rng.shuffle(cycle)
    print(f"featured footprint: id={overused_id} on {overused_n} posts; pool={len(pool)}")
    for index, post in enumerate(targets):
        pid = int(post["id"])
        new_id = cycle[index % len(cycle)]
        row = {"id": pid, "from": overused_id, "to": new_id, "link": post.get("link")}
        if not execute:
            report["assignments"].append(row)
            continue
        method, code = put_or_post_post(base, user, password, pid, {"featured_media": new_id})
        row["http"] = code
        row["method"] = method
        if code not in (200, 201):
            report["errors"].append(row)
            print(f"featured FAIL post {pid} HTTP {code}")
        else:
            report["assignments"].append(row)
            print(f"featured {method} {pid} {overused_id} -> {new_id}")
        time.sleep(0.08)
    print(f"featured: planned/updated {len(report['assignments'])}, errors {len(report['errors'])}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase 2 Max Art cleanup. Dry-run unless --execute is passed."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform deletes and REST writes. Omit this flag for a report-only dry run.",
    )
    parser.add_argument(
        "--tasks",
        default="1,2,3",
        help="Comma-separated task numbers to run (default: 1,2,3).",
    )
    parser.add_argument("--seed", type=int, default=20260917, help="RNG seed for featured-image assignment.")
    parser.add_argument("--limit", type=int, default=None, help="Cap posts processed in tasks 2 and 3 (testing).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    url, user, password, wp_root = config()
    wanted = {int(part.strip()) for part in args.tasks.split(",") if part.strip()}
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"phase2 {mode} site={url} wp_root={wp_root or '(unset)'}")
    report: dict[str, Any] = {
        "mode": mode.lower(),
        "site": url,
        "wp_root": str(wp_root) if wp_root else None,
        "started": datetime.now(timezone.utc).isoformat(),
        "tasks": {},
    }
    if 1 in wanted:
        print("=== task 1 filesystem ===")
        report["tasks"]["1_filesystem"] = task1_filesystem(
            wp_root, args.execute, url, user, password
        )
    if 2 in wanted:
        print("=== task 2 strip JSON-LD ===")
        report["tasks"]["2_jsonld"] = task2_strip_jsonld(url, user, password, args.execute, args.limit)
    if 3 in wanted:
        print("=== task 3 diversify featured images ===")
        report["tasks"]["3_featured"] = task3_diversify_featured(
            url, user, password, args.execute, args.seed, args.limit
        )
    out = REPO_ROOT / "site" / ("phase2-report.json" if args.execute else "phase2-dry-run.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
