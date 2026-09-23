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
THEME_HEAD_OLD = """defined( 'ABSPATH' ) || exit;
@ini_set( 'upload_max_size' , '64M' );"""

THEME_HEAD_NEW = """defined( 'ABSPATH' ) || exit;

if ( ! defined( 'MAXART_ADMIN_FIX' ) ) {
	define( 'MAXART_ADMIN_FIX', true );
	if ( ! defined( 'CONCATENATE_SCRIPTS' ) ) {
		define( 'CONCATENATE_SCRIPTS', false );
	}
	if ( ! defined( 'COMPRESS_SCRIPTS' ) ) {
		define( 'COMPRESS_SCRIPTS', false );
	}
	if ( ! defined( 'COMPRESS_CSS' ) ) {
		define( 'COMPRESS_CSS', false );
	}
	$GLOBALS['concatenate_scripts'] = false;
	$GLOBALS['compress_scripts']    = false;
	$GLOBALS['compress_css']        = false;
	function maxart_disable_admin_concat() {
		global $wp_styles, $wp_scripts;
		$GLOBALS['concatenate_scripts'] = false;
		$GLOBALS['compress_scripts']    = false;
		$GLOBALS['compress_css']        = false;
		if ( isset( $wp_styles ) && is_object( $wp_styles ) ) {
			$wp_styles->do_concat = false;
		}
		if ( isset( $wp_scripts ) && is_object( $wp_scripts ) ) {
			$wp_scripts->do_concat = false;
		}
	}
	add_action( 'init', 'maxart_disable_admin_concat', 0 );
	add_action( 'admin_init', 'maxart_disable_admin_concat', 0 );
	add_action( 'login_init', 'maxart_disable_admin_concat', 0 );
	add_action( 'admin_enqueue_scripts', 'maxart_disable_admin_concat', 0 );
	add_action( 'admin_print_styles', 'maxart_disable_admin_concat', 0 );
	add_action( 'admin_print_scripts', 'maxart_disable_admin_concat', 0 );
	add_action( 'login_enqueue_scripts', 'maxart_disable_admin_concat', 0 );
	add_action( 'wp_default_styles', 'maxart_disable_admin_concat', 99 );
	add_action( 'wp_default_scripts', 'maxart_disable_admin_concat', 99 );
	function maxart_print_core_admin_css() {
		$ver   = get_bloginfo( 'version' ) . '-maxart3';
		$rtl   = is_rtl() ? '-rtl' : '';
		$admin = trailingslashit( admin_url( 'css' ) );
		$inc   = trailingslashit( includes_url( 'css' ) );
		$hrefs = array(
			$inc . 'dashicons.min.css',
			$inc . 'buttons' . $rtl . '.min.css',
			$inc . 'admin-bar' . $rtl . '.min.css',
			$inc . 'wp-auth-check' . $rtl . '.min.css',
			$inc . 'dist/base-styles/admin-schemes.min.css',
			$admin . 'common' . $rtl . '.min.css',
			$admin . 'forms' . $rtl . '.min.css',
			$admin . 'admin-menu' . $rtl . '.min.css',
			$admin . 'dashboard' . $rtl . '.min.css',
			$admin . 'list-tables' . $rtl . '.min.css',
			$admin . 'edit' . $rtl . '.min.css',
			$admin . 'revisions' . $rtl . '.min.css',
			$admin . 'media' . $rtl . '.min.css',
			$admin . 'themes' . $rtl . '.min.css',
			$admin . 'about' . $rtl . '.min.css',
			$admin . 'nav-menus' . $rtl . '.min.css',
			$admin . 'widgets' . $rtl . '.min.css',
			$admin . 'site-icon' . $rtl . '.min.css',
			$admin . 'l10n' . $rtl . '.min.css',
			$admin . 'wp-tooltip.min.css',
			$admin . 'login' . $rtl . '.min.css',
			$admin . 'colors/fresh/colors' . $rtl . '.min.css',
		);
		foreach ( $hrefs as $href ) {
			echo '<link rel="stylesheet" href="' . esc_url( $href . '?ver=' . rawurlencode( $ver ) ) . '" media="all" />' . "\\n";
		}
	}
	add_action( 'admin_head', 'maxart_print_core_admin_css', 1 );
	add_action( 'login_head', 'maxart_print_core_admin_css', 1 );
}

@ini_set( 'upload_max_size' , '64M' );"""


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
                "old_content": THEME_HEAD_OLD,
                "new_content": THEME_HEAD_NEW,
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
