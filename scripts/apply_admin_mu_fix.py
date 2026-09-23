#!/usr/bin/env python3
"""Restore the wp-admin WAF/concat fix after a KAYAN theme overwrite.

Tries, in order:
1. wp-content/mu-plugins/maxart-admin-fix.php (survives theme updates)
2. WPVibe code-snippet
3. Append the same PHP to the live theme functions.php
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import cli, config, log_cli, request  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MU_PLUGIN = ROOT / "scripts" / "mu-plugins" / "maxart-admin-fix.php"
THEME_TAIL = """function kayan_send_404_status() {
	if ( is_404() ) {
		status_header( 404 );
		nocache_headers();
	}
}
add_action( 'wp', 'kayan_send_404_status', 1 );
// ============================================================
"""


def snippet_body() -> str:
    text = MU_PLUGIN.read_text(encoding="utf-8")
    # WPCode/snippets usually wrap with <?php themselves.
    if text.startswith("<?php"):
        text = text.split("\n", 1)[1]
    return text.strip() + "\n"


def try_mu_plugin(url: str, user: str, password: str, content: str) -> bool:
    payloads = [
        {"path": "mu-plugins/maxart-admin-fix.php", "content": content, "scope": "wp-content"},
        {"path": "wp-content/mu-plugins/maxart-admin-fix.php", "content": content},
        {"path": "mu-plugins/maxart-admin-fix.php", "content": content},
    ]
    for payload in payloads:
        try:
            data = request(
                f"{url}/wp-json/wpvibe/v1/file/write",
                user,
                password,
                method="POST",
                payload=payload,
            )
            print("mu-plugin write", payload.get("path"), json.dumps(data, ensure_ascii=False)[:600])
            return True
        except Exception as exc:  # noqa: BLE001
            print("mu-plugin write fail", payload.get("path"), str(exc)[:400])
    return False


def try_code_snippet(url: str, user: str, password: str, code: str) -> bool:
    for location in ("everywhere", "admin", "run_everywhere", "plugins_loaded", "init"):
        try:
            data = request(
                f"{url}/wp-json/wpvibe/v1/code-snippet",
                user,
                password,
                method="POST",
                payload={
                    "action": "create",
                    "title": "Max Art Admin WAF Fix",
                    "code": code,
                    "code_type": "php",
                    "location": location,
                    "insert_method": "auto",
                },
            )
            print("code-snippet", location, json.dumps(data, ensure_ascii=False)[:800])
            return True
        except Exception as exc:  # noqa: BLE001
            print("code-snippet fail", location, str(exc)[:400])
    return False


def append_theme_functions(url: str, user: str, password: str, code: str) -> None:
    print("draft-theme")
    draft = request(f"{url}/wp-json/wpvibe/v1/draft-theme", user, password, method="POST", payload={})
    print("draft", json.dumps(draft, ensure_ascii=False)[:500] if isinstance(draft, dict) else draft)

    live = request(
        f"{url}/wp-json/wpvibe/v1/file/search",
        user,
        password,
        method="POST",
        payload={"pattern": "maxart_print_core_admin_css", "extensions": ["php"], "max_results": 5},
    )
    matches = (live or {}).get("total_matches") if isinstance(live, dict) else None
    print("existing theme matches", matches)
    if matches:
        print("functions.php already has the admin CSS helper")
    else:
        edited = request(
            f"{url}/wp-json/wpvibe/v1/file/edit",
            user,
            password,
            method="POST",
            payload={
                "path": "functions.php",
                "old_content": THEME_TAIL,
                "new_content": THEME_TAIL + "\n" + code,
            },
        )
        print("functions.php edit", json.dumps(edited, ensure_ascii=False)[:800] if not isinstance(edited, str) else edited[:800])

    pub = request(f"{url}/wp-json/wpvibe/v1/draft-theme/publish", user, password, method="POST", payload={})
    print("publish", json.dumps(pub, ensure_ascii=False)[:800] if isinstance(pub, dict) else pub)


def main() -> int:
    url, user, password = config()
    full = MU_PLUGIN.read_text(encoding="utf-8")
    code = snippet_body()
    print("deploy admin WAF fix")

    mu_ok = try_mu_plugin(url, user, password, full)
    snippet_ok = False
    if not mu_ok:
        snippet_ok = try_code_snippet(url, user, password, code)

    # Always restore functions.php so the dashboard is fixed even if mu-plugin/snippet
    # need extra approval. function_exists() keeps a double-load safe.
    append_theme_functions(url, user, password, code)

    log_cli("purge", cli(url, user, password, "cache purge all", confirm=True))
    print("done mu_ok=", mu_ok, "snippet_ok=", snippet_ok)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
