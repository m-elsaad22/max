#!/usr/bin/env python3
"""Publish a stronger wp-admin CSS fix to the live KAYAN theme."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import cli, config, log_cli, request  # noqa: E402

OLD_CONCAT = """if ( ! defined( 'CONCATENATE_SCRIPTS' ) ) {
	define( 'CONCATENATE_SCRIPTS', false );
}
$GLOBALS['concatenate_scripts'] = false;

function maxart_disable_admin_concat() {
	$GLOBALS['concatenate_scripts'] = false;
	$GLOBALS['compress_scripts']    = false;
	$GLOBALS['compress_css']        = false;
}
add_action( 'init', 'maxart_disable_admin_concat', 0 );
add_action( 'admin_init', 'maxart_disable_admin_concat', 0 );
add_action( 'login_init', 'maxart_disable_admin_concat', 0 );"""

NEW_CONCAT = """if ( ! defined( 'CONCATENATE_SCRIPTS' ) ) {
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
	$ver = get_bloginfo( 'version' ) . '-maxart2';
	$rtl = is_rtl() ? '-rtl' : '';
	$admin = trailingslashit( admin_url( 'css' ) );
	$inc   = trailingslashit( includes_url( 'css' ) );
	$hrefs = array(
		$inc . 'dashicons.min.css',
		$inc . 'buttons' . $rtl . '.min.css',
		$inc . 'admin-bar' . $rtl . '.min.css',
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
	);
	foreach ( $hrefs as $href ) {
		echo '<link rel="stylesheet" href="' . esc_url( $href . '?ver=' . rawurlencode( $ver ) ) . '" media="all" />' . "\\n";
	}
}
add_action( 'admin_head', 'maxart_print_core_admin_css', 1 );
add_action( 'login_head', 'maxart_print_core_admin_css', 1 );"""

OLD_STRIP = """function remove_script_version($src) {
    if ( ! is_string( $src ) ) {
        return $src;
    }
    if ( false !== strpos( $src, 'rank-math' ) || false !== strpos( $src, 'seo-by-rank-math' ) ) {
        return $src;
    }"""

NEW_STRIP = """function remove_script_version($src) {
    if ( ! is_string( $src ) ) {
        return $src;
    }
    if ( is_admin() || ( function_exists( 'wp_doing_ajax' ) && wp_doing_ajax() ) ) {
        return $src;
    }
    if ( false !== strpos( $src, '/wp-admin/' ) || false !== strpos( $src, '/wp-includes/' ) ) {
        return $src;
    }
    if ( false !== strpos( $src, 'rank-math' ) || false !== strpos( $src, 'seo-by-rank-math' ) ) {
        return $src;
    }"""

OLD_CSS_STRIP = """function remove_css_version($src) {
    if ( ! is_string( $src ) ) {
        return $src;
    }
    if ( false !== strpos( $src, 'rank-math' ) || false !== strpos( $src, 'seo-by-rank-math' ) ) {
        return $src;
    }"""

NEW_CSS_STRIP = """function remove_css_version($src) {
    if ( ! is_string( $src ) ) {
        return $src;
    }
    if ( is_admin() || ( function_exists( 'wp_doing_ajax' ) && wp_doing_ajax() ) ) {
        return $src;
    }
    if ( false !== strpos( $src, '/wp-admin/' ) || false !== strpos( $src, '/wp-includes/' ) ) {
        return $src;
    }
    if ( false !== strpos( $src, 'rank-math' ) || false !== strpos( $src, 'seo-by-rank-math' ) ) {
        return $src;
    }"""

OLD_DEREG = """function wps_deregister_styles() {
    wp_dequeue_style( 'wp-block-library' );
}"""

NEW_DEREG = """function wps_deregister_styles() {
    if ( is_admin() ) {
        return;
    }
    wp_dequeue_style( 'wp-block-library' );
}"""


def edit(url, user, password, path: str, old: str, new: str) -> None:
    data = request(
        f"{url}/wp-json/wpvibe/v1/file/edit",
        user,
        password,
        method="POST",
        payload={"path": path, "old_content": old, "new_content": new},
    )
    print("edit", path, json.dumps(data, ensure_ascii=False)[:800] if not isinstance(data, str) else data[:800])


def main() -> int:
    url, user, password = config()
    print("draft-theme")
    draft = request(f"{url}/wp-json/wpvibe/v1/draft-theme", user, password, method="POST", payload={})
    print("draft", json.dumps(draft, ensure_ascii=False)[:600] if isinstance(draft, dict) else draft)

    print("edit functions.php concat")
    edit(url, user, password, "functions.php", OLD_CONCAT, NEW_CONCAT)

    print("edit Enqueues version strip")
    edit(url, user, password, "components/packs/Enqueues/setup.php", OLD_STRIP, NEW_STRIP)
    edit(url, user, password, "components/packs/Enqueues/setup.php", OLD_CSS_STRIP, NEW_CSS_STRIP)
    edit(url, user, password, "components/packs/Enqueues/setup.php", OLD_DEREG, NEW_DEREG)

    print("publish")
    pub = request(f"{url}/wp-json/wpvibe/v1/draft-theme/publish", user, password, method="POST", payload={})
    print("publish", json.dumps(pub, ensure_ascii=False)[:800] if isinstance(pub, dict) else pub)

    log_cli("purge", cli(url, user, password, "litespeed-purge all", confirm=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
