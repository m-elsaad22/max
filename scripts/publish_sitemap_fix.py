#!/usr/bin/env python3
"""Restore Rank Math XML sitemaps and robots.txt on max-art-ae.com."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import cli, config, log_cli, request  # noqa: E402

FUNCTIONS_TAIL = """$__maxart_ads_landing = __DIR__ . '/maxart-ads-landing.php';
if ( is_readable( $__maxart_ads_landing ) ) {
	require_once $__maxart_ads_landing;
}"""

SITEMAP_SNIPPET = r'''
add_action( 'init', 'maxart_sitemap_rewrite_rules', 2 );
function maxart_sitemap_rewrite_rules() {
	add_rewrite_rule( 'sitemap_index\.xml$', 'index.php?sitemap=1', 'top' );
	add_rewrite_rule( '([^/]+?)-sitemap([0-9]+)?\.xml$', 'index.php?sitemap=$matches[1]&sitemap_n=$matches[2]', 'top' );
	add_rewrite_rule( '([a-z]+)?-?sitemap\.xsl$', 'index.php?xsl=$matches[1]', 'top' );
}
add_filter( 'robots_txt', 'maxart_robots_txt_map', 99, 2 );
function maxart_robots_txt_map( $output, $public ) {
	if ( ! $public ) {
		return $output;
	}
	return "User-agent: *\nAllow: /\n\nSitemap: https://max-art-ae.com/sitemap_index.xml\n";
}
add_action( 'init', 'maxart_sitemap_maybe_flush', 99 );
function maxart_sitemap_maybe_flush() {
	$rules = get_option( 'rewrite_rules' );
	if ( is_array( $rules ) && isset( $rules['sitemap_index\\.xml$'] ) && get_option( 'maxart_sitemap_fix_ver' ) === '1' ) {
		return;
	}
	flush_rewrite_rules( false );
	update_option( 'maxart_sitemap_fix_ver', '1', true );
}
add_action( 'init', 'maxart_remove_legacy_sitemap_file', 0 );
function maxart_remove_legacy_sitemap_file() {
	$path = trailingslashit( ABSPATH ) . 'sitemap.xml';
	if ( is_file( $path ) ) {
		wp_delete_file( $path );
	}
}
add_action( 'pre_get_posts', 'maxart_sitemap_skip_polylang_lang', 1 );
function maxart_sitemap_skip_polylang_lang( $q ) {
	if ( is_object( $q ) && ( $q->get( 'sitemap' ) || ! empty( $q->query_vars['sitemap'] ) ) ) {
		$q->set( 'lang', '' );
	}
}
add_filter( 'pll_filter_query_excluded_query_vars', 'maxart_pll_exclude_sitemap_qv' );
function maxart_pll_exclude_sitemap_qv( $qv ) {
	$qv[] = 'sitemap';
	$qv[] = 'sitemap_n';
	return $qv;
}
'''


def write_theme_files(url: str, user: str, password: str) -> None:
    print("draft-theme")
    draft = request(f"{url}/wp-json/wpvibe/v1/draft-theme", user, password, method="POST", payload={})
    print("draft", json.dumps(draft, ensure_ascii=False)[:400] if isinstance(draft, dict) else draft)

    live = request(f"{url}/wp-json/wpvibe/v1/file/read", user, password, method="POST", payload={"path": "functions.php"})
    functions = (live or {}).get("content") if isinstance(live, dict) else ""
    if "maxart_sitemap_rewrite_rules" in (functions or ""):
        print("functions.php already has sitemap rewrites")
    elif FUNCTIONS_TAIL in (functions or ""):
        edited = request(
            f"{url}/wp-json/wpvibe/v1/file/edit",
            user,
            password,
            method="POST",
            payload={
                "path": "functions.php",
                "old_content": FUNCTIONS_TAIL,
                "new_content": FUNCTIONS_TAIL + SITEMAP_SNIPPET,
            },
        )
        print("functions edit", json.dumps(edited, ensure_ascii=False)[:500] if not isinstance(edited, str) else edited[:500])
    else:
        raise SystemExit("functions.php tail did not match; refusing to append sitemap hooks")

    pub = request(f"{url}/wp-json/wpvibe/v1/draft-theme/publish", user, password, method="POST", payload={})
    print("publish", json.dumps(pub, ensure_ascii=False)[:800] if isinstance(pub, dict) else pub)


def main() -> int:
    url, user, password = config()
    print("publish sitemap + robots fix")
    write_theme_files(url, user, password)
    log_cli("page sitemap", cli(url, user, password, "option patch update rank-math-options-sitemap pt_page_sitemap on", confirm=True))
    log_cli("services sitemap", cli(url, user, password, "option patch update rank-math-options-sitemap pt_services_sitemap on", confirm=True))
    log_cli("rewrite", cli(url, user, password, "rewrite flush", confirm=True))
    log_cli("purge", cli(url, user, password, "cache purge all", confirm=True))
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
