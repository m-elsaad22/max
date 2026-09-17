#!/usr/bin/env python3
"""Phase 2 — filesystem cleanup, JSON-LD extraction, featured-image diversification.

Default mode is a dry run (no deletes, no REST writes). Pass --apply to execute.

Credentials (any alias works) from the environment or /.env:
  WP_BASE_URL | WP_URL
  WP_USERNAME | WP_USER
  WP_APP_PASSWORD
  WP_ROOT          absolute path to the WordPress document root (Task 1)

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
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
UA = "max-art-phase2-cleanup/1.0"
DEFAULT_URL = "https://max-art-ae.com"

# Real disk names on max-art-ae.com, plus the names requested in the brief.
PLUGIN_FOLDERS = (
    "wordpress-seo",  # Yoast
    "weglot",
    "mpg-multiple-pages-generator",  # requested name (may not exist)
    "multiple-pages-generator-by-porthas",  # actual Themeisle/Porthas folder
)
SITEMAP_NAME = "mpg-sitemap-plumbing-services.xml"
NEVER_DELETE_PLUGINS = {
    "seo-by-rank-math",
    "litespeed-cache",
    "vibe-ai",
    "classic-editor",
    "classic-widgets",
    "tinymce-advanced",
}
# Site logo used as a navy block on pages — keep it out of the rotation pool.
EXCLUDE_MEDIA_IDS = {3362, 0}

LD_JSON_RE = re.compile(
    r"<script\b[^>]*\btype\s*=\s*['\"]application/ld\+json['\"][^>]*>.*?</script>",
    re.I | re.S,
)
LD_COMMENT_RE = re.compile(
    r"<!--\s*Schema\.org JSON-LD[^>]*-->\s*",
    re.I,
)


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def config() -> tuple[str, str, str]:
    load_dotenv(ROOT / ".env")
    url = (
        os.environ.get("WP_BASE_URL")
        or os.environ.get("WP_URL")
        or DEFAULT_URL
    ).rstrip("/")
    user = (os.environ.get("WP_USERNAME") or os.environ.get("WP_USER") or "").strip()
    password = (os.environ.get("WP_APP_PASSWORD") or "").strip()
    if not user or not password:
        sys.exit("Missing WP_USERNAME/WP_USER or WP_APP_PASSWORD in the environment or .env")
    return url, user, password


def wp_root() -> Path | None:
    load_dotenv(ROOT / ".env")
    raw = (os.environ.get("WP_ROOT") or "").strip()
    return Path(raw) if raw else None


def _auth_header(user: str, password: str) -> str:
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
        "Authorization": _auth_header(user, password),
        "Accept": "application/json",
        "User-Agent": UA,
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
            try:
                parsed = json.loads(detail)
            except json.JSONDecodeError:
                parsed = detail
            if exc.code in {429, 500, 502, 503, 504} and attempt < 4:
                time.sleep(1.6 * (attempt + 1))
                last = RuntimeError(f"HTTP {exc.code} {method} {url}")
                continue
            raise RuntimeError(f"HTTP {exc.code} {method} {url}\n{str(parsed)[:2000]}") from exc
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


def paginate(
    base: str,
    user: str,
    password: str,
    path: str,
    per_page: int = 50,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    sep = "&" if "?" in path else "?"
    while True:
        code, hdrs, data = rest(
            base,
            user,
            password,
            f"{path}{sep}per_page={per_page}&page={page}",
        )
        if code != 200 or not isinstance(data, list):
            break
        items.extend(data)
        total_pages = int(hdrs.get("x-wp-totalpages") or "1")
        print(f"  fetched page {page}/{total_pages} ({len(data)} items)", flush=True)
        if page >= total_pages or len(data) < per_page:
            break
        page += 1
        time.sleep(0.08)
    return items


# ---------------------------------------------------------------------------
# Task 1 — local filesystem
# ---------------------------------------------------------------------------

def task_filesystem(apply: bool) -> dict[str, Any]:
    report: dict[str, Any] = {"root": None, "deleted": [], "missing": [], "skipped": []}
    root = wp_root()
    if root is None:
        print("Task 1: WP_ROOT is not set — skipping local deletes.")
        print("         Set WP_ROOT to the WordPress document root (the folder that contains wp-config.php).")
        report["skipped"].append("WP_ROOT unset")
        return report
    if not root.is_dir():
        print(f"Task 1: WP_ROOT does not exist: {root}")
        report["skipped"].append(f"missing root {root}")
        return report
    if not (root / "wp-config.php").is_file() and not (root / "wp-content").is_dir():
        print(f"Task 1: {root} does not look like a WordPress root (no wp-config.php / wp-content). Aborting deletes.")
        report["skipped"].append("not a wordpress root")
        return report

    report["root"] = str(root)
    targets: list[Path] = [root / SITEMAP_NAME]
    plugins = root / "wp-content" / "plugins"
    for folder in PLUGIN_FOLDERS:
        if folder in NEVER_DELETE_PLUGINS:
            report["skipped"].append(folder)
            continue
        targets.append(plugins / folder)

    for path in targets:
        if not path.exists():
            print(f"  skip (not found): {path}")
            report["missing"].append(str(path))
            continue
        print(f"  {'DELETE' if apply else 'dry-run delete'}: {path}")
        if not apply:
            report["deleted"].append({"path": str(path), "applied": False})
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            report["deleted"].append({"path": str(path), "applied": True})
        except OSError as exc:
            print(f"  ERROR deleting {path}: {exc}")
            report["skipped"].append(f"{path}: {exc}")
    return report


# ---------------------------------------------------------------------------
# Task 2 — JSON-LD extraction
# ---------------------------------------------------------------------------

def extract_ld_json(html: str) -> tuple[str, list[Any]]:
    """Return (cleaned_html, list of parsed or raw schema payloads)."""
    schemas: list[Any] = []

    def _consume(match: re.Match[str]) -> str:
        block = match.group(0)
        inner_match = re.search(r"<script\b[^>]*>(.*)</script>", block, flags=re.I | re.S)
        inner = (inner_match.group(1) if inner_match else "").strip()
        try:
            schemas.append(json.loads(inner))
        except json.JSONDecodeError:
            schemas.append({"_raw": inner})
        return ""

    cleaned = LD_JSON_RE.sub(_consume, html)
    cleaned = LD_COMMENT_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if cleaned:
        cleaned += "\n"
    return cleaned, schemas


def task_schema(
    base: str,
    user: str,
    password: str,
    apply: bool,
    backup_path: Path,
    types: tuple[str, ...],
) -> dict[str, Any]:
    backup: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": not apply,
        "posts": [],
    }
    stats = {"scanned": 0, "with_schema": 0, "updated": 0, "failed": 0, "unchanged": 0}

    for ptype in types:
        path = "/wp/v2/posts" if ptype == "post" else f"/wp/v2/{ptype}"
        print(f"Task 2: listing {ptype} …")
        try:
            items = paginate(base, user, password, f"{path}?status=publish&context=edit")
        except RuntimeError as exc:
            if "rest_no_route" in str(exc) or "HTTP 404" in str(exc):
                print(f"  no REST route for {ptype}, skipping")
                continue
            raise
        for item in items:
            stats["scanned"] += 1
            pid = int(item["id"])
            raw = ((item.get("content") or {}).get("raw")) or ""
            if "application/ld+json" not in raw.lower():
                stats["unchanged"] += 1
                continue
            cleaned, schemas = extract_ld_json(raw)
            if not schemas:
                stats["unchanged"] += 1
                continue
            stats["with_schema"] += 1
            backup["posts"].append(
                {
                    "id": pid,
                    "type": ptype,
                    "link": item.get("link"),
                    "title": ((item.get("title") or {}).get("raw") or ""),
                    "schemas": schemas,
                }
            )
            if cleaned == raw:
                continue
            print(f"  {'PUT' if apply else 'dry-run'} #{pid} remove {len(schemas)} JSON-LD block(s)")
            if not apply:
                continue
            try:
                rest(
                    base,
                    user,
                    password,
                    f"{path}/{pid}",
                    method="PUT",
                    payload={"content": cleaned},
                )
                stats["updated"] += 1
            except RuntimeError as exc:
                print(f"  PUT failed #{pid}: {exc}")
                try:
                    rest(
                        base,
                        user,
                        password,
                        f"{path}/{pid}",
                        method="POST",
                        payload={"content": cleaned},
                    )
                    stats["updated"] += 1
                    print(f"  POST fallback ok #{pid}")
                except RuntimeError as exc2:
                    stats["failed"] += 1
                    print(f"  POST fallback failed #{pid}: {exc2}")
            time.sleep(0.05)

    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Task 2: wrote {backup_path} ({stats['with_schema']} posts with in-body schema)")
    return {"stats": stats, "backup": str(backup_path)}


# ---------------------------------------------------------------------------
# Task 3 — featured image diversification
# ---------------------------------------------------------------------------

def task_featured_images(
    base: str,
    user: str,
    password: str,
    apply: bool,
    seed: int,
) -> dict[str, Any]:
    print("Task 3: media library …")
    media = paginate(base, user, password, "/wp/v2/media?media_type=image")
    pool = sorted(
        {
            int(m["id"])
            for m in media
            if str(m.get("mime_type") or "").startswith("image/")
            and int(m["id"]) not in EXCLUDE_MEDIA_IDS
        }
    )
    print(f"  image pool: {len(pool)} ids")

    print("Task 3: published posts …")
    posts = paginate(base, user, password, "/wp/v2/posts?status=publish&context=edit")
    counts: Counter[int] = Counter(int(p.get("featured_media") or 0) for p in posts)
    if not counts:
        return {"targets": 0, "dominant_id": None, "updated": 0}

    dominant_id, dominant_n = counts.most_common(1)[0]
    print(f"  most-used featured_media={dominant_id} on {dominant_n} posts")
    if dominant_id == 0:
        print("  dominant id is 0 (no image) — nothing to diversify.")
        return {"targets": 0, "dominant_id": 0, "updated": 0, "note": "no featured image"}

    assign_pool = [mid for mid in pool if mid != dominant_id]
    if not assign_pool:
        print("  no alternative images in the library. Aborting reassignment.")
        return {
            "targets": dominant_n,
            "dominant_id": dominant_id,
            "updated": 0,
            "note": "empty alternate pool",
        }

    rng = random.Random(seed)
    rng.shuffle(assign_pool)
    targets = [p for p in posts if int(p.get("featured_media") or 0) == dominant_id]
    # even round-robin over the shuffled pool
    updated = 0
    failed = 0
    plan: list[tuple[int, int]] = []
    for i, post in enumerate(targets):
        plan.append((int(post["id"]), assign_pool[i % len(assign_pool)]))

    dist: dict[int, int] = defaultdict(int)
    for pid, new_id in plan:
        dist[new_id] += 1
        print(f"  {'POST featured_media' if apply else 'dry-run'} #{pid} {dominant_id} -> {new_id}")
        if not apply:
            continue
        try:
            rest(
                base,
                user,
                password,
                f"/wp/v2/posts/{pid}",
                method="POST",
                payload={"featured_media": new_id},
            )
            updated += 1
        except RuntimeError as exc:
            failed += 1
            print(f"  featured_media failed #{pid}: {exc}")
        time.sleep(0.04)

    return {
        "dominant_id": dominant_id,
        "dominant_count": dominant_n,
        "targets": len(targets),
        "pool_size": len(assign_pool),
        "updated": updated,
        "failed": failed,
        "per_image_assignment": dict(dist),
        "seed": seed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 2 filesystem + schema + featured-image cleanup")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute deletes and REST writes. Default is dry-run.",
    )
    parser.add_argument(
        "--tasks",
        default="fs,schema,media",
        help="Comma list: fs, schema, media (default: all three)",
    )
    parser.add_argument("--types", default="post", help="REST types for schema pass (default: post)")
    parser.add_argument("--seed", type=int, default=20260917, help="RNG seed for even image assignment")
    parser.add_argument(
        "--backup",
        default=str(ROOT / "site" / "schemas_backup.json"),
        help="Where to write extracted JSON-LD",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    apply = bool(args.apply)
    tasks = {t.strip() for t in args.tasks.split(",") if t.strip()}
    print(f"phase2 mode={'APPLY' if apply else 'DRY-RUN'} tasks={sorted(tasks)}")
    url, user, password = config()
    print(f"site {url} user {user}")

    summary: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "site": url,
        "started": datetime.now(timezone.utc).isoformat(),
    }
    if "fs" in tasks:
        summary["filesystem"] = task_filesystem(apply)
    if "schema" in tasks:
        types = tuple(t.strip() for t in args.types.split(",") if t.strip())
        summary["schema"] = task_schema(url, user, password, apply, Path(args.backup), types)
    if "media" in tasks:
        summary["featured_images"] = task_featured_images(url, user, password, apply, args.seed)

    out = ROOT / "site" / "phase2-report.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
