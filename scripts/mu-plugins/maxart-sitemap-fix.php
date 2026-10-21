<?php
/**
 * Plugin Name: Max Art Sitemap Fix
 * Description: Restores Rank Math XML sitemap permalinks, points robots.txt at sitemap_index.xml, and removes the legacy static sitemap.xml.
 * Version: 1.0.0
 *
 * Canonical source for the block inserted into the live theme functions.php.
 * Re-apply after a KAYAN overwrite with: python3 scripts/publish_sitemap_fix.py
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( defined( 'MAXART_SITEMAP_FIX' ) ) {
	return;
}
define( 'MAXART_SITEMAP_FIX', true );

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
