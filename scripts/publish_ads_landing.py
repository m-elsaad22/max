#!/usr/bin/env python3
"""Publish the ads landing page and IP tracker on max-art-ae.com."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import cli, config, log_cli, request, rest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ADS_HTML = ROOT / "scripts" / "ads-landing" / "ads.html"
ADS_PHP = ROOT / "scripts" / "ads-landing" / "maxart-ads-landing.php"

REQUIRE_BLOCK = """
$__maxart_ads_landing = __DIR__ . '/maxart-ads-landing.php';
if ( is_readable( $__maxart_ads_landing ) ) {
	require_once $__maxart_ads_landing;
}
"""

FUNCTIONS_TAIL = """add_action( 'admin_head', 'maxart_print_core_admin_css', 1 );
add_action( 'login_head', 'maxart_print_core_admin_css', 1 );"""


def try_plugin_write(url: str, user: str, password: str) -> bool:
    payloads = [
        {
            "path": "plugins/maxart-ads-tracker/maxart-ads-landing.php",
            "content": ADS_PHP.read_text(encoding="utf-8"),
            "scope": "wp-content",
        },
        {
            "path": "plugins/maxart-ads-tracker/ads.html",
            "content": ADS_HTML.read_text(encoding="utf-8"),
            "scope": "wp-content",
        },
    ]
    ok = True
    for payload in payloads:
        try:
            data = request(
                f"{url}/wp-json/wpvibe/v1/file/write",
                user,
                password,
                method="POST",
                payload=payload,
            )
            print("plugin write", payload["path"], json.dumps(data, ensure_ascii=False)[:400])
        except Exception as exc:  # noqa: BLE001
            print("plugin write fail", payload["path"], str(exc)[:400])
            ok = False
    if ok:
        log_cli("activate", cli(url, user, password, "plugin activate maxart-ads-tracker/maxart-ads-landing.php", confirm=True))
    return ok


def write_theme_files(url: str, user: str, password: str) -> None:
    print("draft-theme")
    draft = request(f"{url}/wp-json/wpvibe/v1/draft-theme", user, password, method="POST", payload={})
    print("draft", json.dumps(draft, ensure_ascii=False)[:400] if isinstance(draft, dict) else draft)

    for path, content in (
        ("ads.html", ADS_HTML.read_text(encoding="utf-8")),
        ("maxart-ads-landing.php", ADS_PHP.read_text(encoding="utf-8")),
    ):
        data = request(
            f"{url}/wp-json/wpvibe/v1/file/write",
            user,
            password,
            method="POST",
            payload={"path": path, "content": content},
        )
        print("theme write", path, json.dumps(data, ensure_ascii=False)[:400] if not isinstance(data, str) else data[:400])

    live = request(f"{url}/wp-json/wpvibe/v1/file/read", user, password, method="POST", payload={"path": "functions.php"})
    functions = (live or {}).get("content") if isinstance(live, dict) else ""
    if "maxart-ads-landing.php" not in (functions or ""):
        if FUNCTIONS_TAIL in functions:
            edited = request(
                f"{url}/wp-json/wpvibe/v1/file/edit",
                user,
                password,
                method="POST",
                payload={
                    "path": "functions.php",
                    "old_content": FUNCTIONS_TAIL,
                    "new_content": FUNCTIONS_TAIL + REQUIRE_BLOCK,
                },
            )
            print("functions edit", json.dumps(edited, ensure_ascii=False)[:500] if not isinstance(edited, str) else edited[:500])
        else:
            write = request(
                f"{url}/wp-json/wpvibe/v1/file/write",
                user,
                password,
                method="POST",
                payload={"path": "functions.php", "content": (functions or "") + REQUIRE_BLOCK},
            )
            print("functions append-write", json.dumps(write, ensure_ascii=False)[:500] if not isinstance(write, str) else write[:500])
    else:
        print("functions.php already requires ads landing")

    pub = request(f"{url}/wp-json/wpvibe/v1/draft-theme/publish", user, password, method="POST", payload={})
    print("publish", json.dumps(pub, ensure_ascii=False)[:800] if isinstance(pub, dict) else pub)


def ensure_page(url: str, user: str, password: str) -> int:
    existing = rest(url, user, password, "/wp/v2/pages?slug=ads&status=publish,draft,private")
    payload = {
        "title": "كشف تسربات المياه وعزل الأسطح",
        "slug": "ads",
        "status": "publish",
        "content": "صفحة إعلانات كشف تسربات المياه وعزل الأسطح في الإمارات. التصميم الكامل يظهر على /ads/ و /ads.html.",
    }
    if isinstance(existing, list) and existing:
        page_id = int(existing[0]["id"])
        data = rest(url, user, password, f"/wp/v2/pages/{page_id}", method="POST", payload=payload)
        print("page update", page_id, data.get("link") if isinstance(data, dict) else data)
        return page_id
    data = rest(url, user, password, "/wp/v2/pages", method="POST", payload=payload)
    page_id = int(data["id"]) if isinstance(data, dict) else 0
    print("page create", page_id, data.get("link") if isinstance(data, dict) else data)
    return page_id


def main() -> int:
    url, user, password = config()
    print("publish ads landing + IP tracker")
    plugin_ok = try_plugin_write(url, user, password)
    write_theme_files(url, user, password)
    page_id = ensure_page(url, user, password)
    if page_id:
        log_cli(
            "rankmath title",
            cli(url, user, password, f"post meta update {page_id} rank_math_title 'كشف تسربات المياه وعزل الأسطح في الإمارات | ماكس آرت'", confirm=True),
        )
        log_cli(
            "rankmath desc",
            cli(
                url,
                user,
                password,
                f"post meta update {page_id} rank_math_description 'كشف تسربات المياه دون تكسير عشوائي وعزل أسطح مائي وحراري في الإمارات. معاينة مجانية وضمان مكتوب.'",
                confirm=True,
            ),
        )
    log_cli("rewrite", cli(url, user, password, "rewrite flush", confirm=True))
    log_cli("purge", cli(url, user, password, "cache purge all", confirm=True))
    print("done plugin_ok=", plugin_ok, "page_id=", page_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
