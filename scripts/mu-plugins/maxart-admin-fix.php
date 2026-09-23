<?php
/**
 * Plugin Name: Max Art Admin WAF Fix
 * Description: Loads core wp-admin CSS as individual files so LiteSpeed/WAF cannot break the dashboard via load-styles.php 403.
 * Version: 1.0.0
 *
 * Must-use plugin: survives KAYAN theme updates. Place in wp-content/mu-plugins/.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

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

if ( ! function_exists( 'maxart_disable_admin_concat' ) ) {
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

if ( ! function_exists( 'maxart_print_core_admin_css' ) ) {
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
			echo '<link rel="stylesheet" href="' . esc_url( $href . '?ver=' . rawurlencode( $ver ) ) . '" media="all" />' . "\n";
		}
	}
}

add_action( 'admin_head', 'maxart_print_core_admin_css', 1 );
add_action( 'login_head', 'maxart_print_core_admin_css', 1 );
