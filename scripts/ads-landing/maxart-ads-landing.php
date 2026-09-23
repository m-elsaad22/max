<?php
/**
 * Plugin Name: Max Art Ads Tracker
 * Description: Publishes the ads landing page and logs visitor IP plus Call/WhatsApp clicks.
 * Version: 1.0.0
 *
 * Works as a normal plugin, an mu-plugin, or a theme include.
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

if ( defined( 'MAXART_ADS_TRACKER' ) ) {
	return;
}
define( 'MAXART_ADS_TRACKER', true );

define( 'MAXART_ADS_VERSION', '1.0.0' );
define( 'MAXART_ADS_REWRITE', '1' );

function maxart_ads_table() {
	global $wpdb;
	return $wpdb->prefix . 'maxart_ads_events';
}

function maxart_ads_install() {
	global $wpdb;
	$table   = maxart_ads_table();
	$charset = $wpdb->get_charset_collate();
	$sql     = "CREATE TABLE {$table} (
		id bigint(20) unsigned NOT NULL AUTO_INCREMENT,
		created_at datetime NOT NULL,
		event varchar(32) NOT NULL,
		ip varchar(45) NOT NULL,
		device_id varchar(64) NOT NULL DEFAULT '',
		user_agent varchar(500) NOT NULL DEFAULT '',
		device_label varchar(190) NOT NULL DEFAULT '',
		page varchar(190) NOT NULL DEFAULT '',
		href varchar(255) NOT NULL DEFAULT '',
		referrer varchar(255) NOT NULL DEFAULT '',
		utm varchar(255) NOT NULL DEFAULT '',
		PRIMARY KEY  (id),
		KEY event (event),
		KEY ip (ip),
		KEY created_at (created_at)
	) {$charset};";
	require_once ABSPATH . 'wp-admin/includes/upgrade.php';
	dbDelta( $sql );
	update_option( 'maxart_ads_db_version', MAXART_ADS_VERSION );
}

function maxart_ads_maybe_install() {
	if ( get_option( 'maxart_ads_db_version' ) !== MAXART_ADS_VERSION ) {
		maxart_ads_install();
	}
}
add_action( 'init', 'maxart_ads_maybe_install', 1 );

function maxart_ads_html_path() {
	$candidates = array(
		__DIR__ . '/ads.html',
		get_stylesheet_directory() . '/ads.html',
		get_template_directory() . '/ads.html',
		WP_CONTENT_DIR . '/plugins/maxart-ads-tracker/ads.html',
	);
	foreach ( $candidates as $path ) {
		if ( is_readable( $path ) ) {
			return $path;
		}
	}
	return '';
}

function maxart_ads_client_ip() {
	$keys = array( 'HTTP_CF_CONNECTING_IP', 'HTTP_X_REAL_IP', 'HTTP_CLIENT_IP', 'HTTP_X_FORWARDED_FOR', 'REMOTE_ADDR' );
	foreach ( $keys as $key ) {
		if ( empty( $_SERVER[ $key ] ) ) {
			continue;
		}
		$parts = preg_split( '/\s*,\s*/', (string) wp_unslash( $_SERVER[ $key ] ) );
		foreach ( $parts as $candidate ) {
			$ip = trim( $candidate );
			if ( filter_var( $ip, FILTER_VALIDATE_IP, FILTER_FLAG_NO_PRIV_RANGE | FILTER_FLAG_NO_RES_RANGE ) ) {
				return $ip;
			}
		}
		$ip = trim( (string) $parts[0] );
		if ( filter_var( $ip, FILTER_VALIDATE_IP ) ) {
			return $ip;
		}
	}
	return '0.0.0.0';
}

function maxart_ads_device_id() {
	$cookie = isset( $_COOKIE['maxart_vid'] ) ? preg_replace( '/[^a-zA-Z0-9_-]/', '', (string) $_COOKIE['maxart_vid'] ) : '';
	if ( strlen( $cookie ) >= 16 ) {
		return substr( $cookie, 0, 64 );
	}
	$id = wp_generate_uuid4();
	if ( ! headers_sent() ) {
		setcookie( 'maxart_vid', $id, time() + YEAR_IN_SECONDS, COOKIEPATH ? COOKIEPATH : '/', COOKIE_DOMAIN, is_ssl(), true );
	}
	$_COOKIE['maxart_vid'] = $id;
	return $id;
}

function maxart_ads_device_label( $ua ) {
	$ua = (string) $ua;
	if ( preg_match( '/iPhone|iPad|iPod/i', $ua ) ) {
		$os = 'Apple';
	} elseif ( preg_match( '/Android/i', $ua ) ) {
		$os = 'Android';
	} elseif ( preg_match( '/Windows/i', $ua ) ) {
		$os = 'Windows';
	} elseif ( preg_match( '/Macintosh|Mac OS/i', $ua ) ) {
		$os = 'Mac';
	} else {
		$os = 'جهاز';
	}
	if ( preg_match( '/Edg\//i', $ua ) ) {
		$browser = 'Edge';
	} elseif ( preg_match( '/Chrome\//i', $ua ) ) {
		$browser = 'Chrome';
	} elseif ( preg_match( '/Safari\//i', $ua ) && ! preg_match( '/Chrome\//i', $ua ) ) {
		$browser = 'Safari';
	} elseif ( preg_match( '/Firefox\//i', $ua ) ) {
		$browser = 'Firefox';
	} else {
		$browser = 'متصفح';
	}
	$type = preg_match( '/Mobile|Android|iPhone/i', $ua ) ? 'جوال' : 'كمبيوتر';
	return $type . ' — ' . $os . ' / ' . $browser;
}

function maxart_ads_log( $event, $extra = array() ) {
	global $wpdb;
	$allowed = array( 'visit', 'call', 'whatsapp' );
	if ( ! in_array( $event, $allowed, true ) ) {
		return false;
	}
	$ip = maxart_ads_client_ip();
	$key = 'maxart_ads_rl_' . md5( $ip . '|' . $event );
	$count = (int) get_transient( $key );
	if ( $count > 40 ) {
		return false;
	}
	set_transient( $key, $count + 1, HOUR_IN_SECONDS );

	$ua  = isset( $_SERVER['HTTP_USER_AGENT'] ) ? substr( sanitize_text_field( wp_unslash( $_SERVER['HTTP_USER_AGENT'] ) ), 0, 500 ) : '';
	$utm = '';
	if ( ! empty( $_GET['utm_source'] ) || ! empty( $_GET['utm_campaign'] ) ) { // phpcs:ignore WordPress.Security.NonceVerification.Recommended
		$utm = substr(
			sanitize_text_field(
				( isset( $_GET['utm_source'] ) ? wp_unslash( $_GET['utm_source'] ) : '' ) . ' / ' . // phpcs:ignore WordPress.Security.NonceVerification.Recommended
				( isset( $_GET['utm_campaign'] ) ? wp_unslash( $_GET['utm_campaign'] ) : '' ) // phpcs:ignore WordPress.Security.NonceVerification.Recommended
			),
			0,
			255
		);
	}
	$wpdb->insert(
		maxart_ads_table(),
		array(
			'created_at'   => current_time( 'mysql' ),
			'event'        => $event,
			'ip'           => substr( $ip, 0, 45 ),
			'device_id'    => maxart_ads_device_id(),
			'user_agent'   => $ua,
			'device_label' => maxart_ads_device_label( $ua ),
			'page'         => isset( $extra['page'] ) ? substr( sanitize_text_field( $extra['page'] ), 0, 190 ) : substr( isset( $_SERVER['REQUEST_URI'] ) ? sanitize_text_field( wp_unslash( $_SERVER['REQUEST_URI'] ) ) : '/ads/', 0, 190 ),
			'href'         => isset( $extra['href'] ) ? substr( esc_url_raw( $extra['href'] ), 0, 255 ) : '',
			'referrer'     => isset( $extra['referrer'] ) ? substr( esc_url_raw( $extra['referrer'] ), 0, 255 ) : ( isset( $_SERVER['HTTP_REFERER'] ) ? substr( esc_url_raw( wp_unslash( $_SERVER['HTTP_REFERER'] ) ), 0, 255 ) : '' ),
			'utm'          => $utm,
		),
		array( '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s' )
	);
	return true;
}

function maxart_ads_is_landing() {
	if ( get_query_var( 'maxart_ads' ) ) {
		return true;
	}
	if ( is_page( 'ads' ) ) {
		return true;
	}
	$request = isset( $_SERVER['REQUEST_URI'] ) ? wp_parse_url( wp_unslash( $_SERVER['REQUEST_URI'] ), PHP_URL_PATH ) : '';
	$request = is_string( $request ) ? untrailingslashit( $request ) : '';
	return in_array( $request, array( '/ads', '/ads.html' ), true );
}

function maxart_ads_render() {
	status_header( 200 );
	header( 'Content-Type: text/html; charset=UTF-8' );
	nocache_headers();
	maxart_ads_log( 'visit' );
	$path = maxart_ads_html_path();
	if ( ! $path ) {
		wp_die( 'صفحة الإعلانات غير متوفرة.' );
	}
	$html = file_get_contents( $path );
	$html = str_replace( '__MAXART_TRACK_URL__', esc_url_raw( rest_url( 'maxart-ads/v1/track' ) ), $html );
	echo $html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped
	exit;
}

function maxart_ads_add_rewrite() {
	add_rewrite_rule( '^ads\.html$', 'index.php?maxart_ads=1', 'top' );
	add_rewrite_rule( '^ads/?$', 'index.php?pagename=ads', 'top' );
	if ( get_option( 'maxart_ads_rewrite' ) !== MAXART_ADS_REWRITE ) {
		flush_rewrite_rules( false );
		update_option( 'maxart_ads_rewrite', MAXART_ADS_REWRITE );
	}
}
add_action( 'init', 'maxart_ads_add_rewrite', 5 );

function maxart_ads_query_vars( $vars ) {
	$vars[] = 'maxart_ads';
	return $vars;
}
add_filter( 'query_vars', 'maxart_ads_query_vars' );

function maxart_ads_template_redirect() {
	if ( maxart_ads_is_landing() ) {
		maxart_ads_render();
	}
}
add_action( 'template_redirect', 'maxart_ads_template_redirect', 0 );

function maxart_ads_rest_track( WP_REST_Request $request ) {
	$params = $request->get_json_params();
	if ( ! is_array( $params ) ) {
		$params = $request->get_params();
	}
	$event = isset( $params['event'] ) ? sanitize_key( $params['event'] ) : '';
	if ( ! in_array( $event, array( 'call', 'whatsapp', 'visit' ), true ) ) {
		return new WP_REST_Response( array( 'ok' => false ), 400 );
	}
	maxart_ads_log(
		$event,
		array(
			'href'     => isset( $params['href'] ) ? $params['href'] : '',
			'page'     => isset( $params['page'] ) ? $params['page'] : '',
			'referrer' => isset( $params['referrer'] ) ? $params['referrer'] : '',
		)
	);
	return new WP_REST_Response( array( 'ok' => true ), 204 );
}

function maxart_ads_register_rest() {
	register_rest_route(
		'maxart-ads/v1',
		'/track',
		array(
			'methods'             => 'POST',
			'permission_callback' => '__return_true',
			'callback'            => 'maxart_ads_rest_track',
		)
	);
}
add_action( 'rest_api_init', 'maxart_ads_register_rest' );

function maxart_ads_event_label( $event ) {
	$map = array(
		'visit'    => 'زيارة الصفحة',
		'call'     => 'ضغط اتصال',
		'whatsapp' => 'ضغط واتساب',
	);
	return isset( $map[ $event ] ) ? $map[ $event ] : $event;
}

function maxart_ads_admin_menu() {
	add_menu_page(
		'تتبع إعلانات كشف التسربات',
		'تتبع الإعلانات',
		'manage_options',
		'maxart-ads-tracker',
		'maxart_ads_admin_page',
		'dashicons-visibility',
		26
	);
}
add_action( 'admin_menu', 'maxart_ads_admin_menu' );

function maxart_ads_admin_page() {
	if ( ! current_user_can( 'manage_options' ) ) {
		return;
	}
	global $wpdb;
	$table = maxart_ads_table();
	$filter = isset( $_GET['event'] ) ? sanitize_key( wp_unslash( $_GET['event'] ) ) : ''; // phpcs:ignore WordPress.Security.NonceVerification.Recommended
	$where  = '1=1';
	$args   = array();
	if ( in_array( $filter, array( 'visit', 'call', 'whatsapp' ), true ) ) {
		$where .= ' AND event = %s';
		$args[] = $filter;
	}
	$sql = "SELECT * FROM {$table} WHERE {$where} ORDER BY id DESC LIMIT 500";
	$rows = $args ? $wpdb->get_results( $wpdb->prepare( $sql, $args ) ) : $wpdb->get_results( $sql );
	$visits = (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$table} WHERE event = 'visit'" );
	$calls  = (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$table} WHERE event = 'call'" );
	$wa     = (int) $wpdb->get_var( "SELECT COUNT(*) FROM {$table} WHERE event = 'whatsapp'" );
	$ips    = (int) $wpdb->get_var( "SELECT COUNT(DISTINCT ip) FROM {$table}" );
	$base   = admin_url( 'admin.php?page=maxart-ads-tracker' );
	echo '<div class="wrap">';
	echo '<h1>تتبع صفحة الإعلانات</h1>';
	echo '<p>كل زيارة لصفحة <a href="' . esc_url( home_url( '/ads/' ) ) . '" target="_blank" rel="noopener">/ads/</a> أو <a href="' . esc_url( home_url( '/ads.html' ) ) . '" target="_blank" rel="noopener">/ads.html</a>، وكل ضغط على اتصال أو واتساب، يُسجَّل مع عنوان IP الجهاز.</p>';
	echo '<p><strong>زيارات:</strong> ' . esc_html( $visits ) . ' — <strong>اتصال:</strong> ' . esc_html( $calls ) . ' — <strong>واتساب:</strong> ' . esc_html( $wa ) . ' — <strong>أجهزة/IP مميزة:</strong> ' . esc_html( $ips ) . '</p>';
	echo '<p>';
	echo '<a class="button' . ( '' === $filter ? ' button-primary' : '' ) . '" href="' . esc_url( $base ) . '">الكل</a> ';
	echo '<a class="button' . ( 'visit' === $filter ? ' button-primary' : '' ) . '" href="' . esc_url( $base . '&event=visit' ) . '">زيارات</a> ';
	echo '<a class="button' . ( 'call' === $filter ? ' button-primary' : '' ) . '" href="' . esc_url( $base . '&event=call' ) . '">اتصال</a> ';
	echo '<a class="button' . ( 'whatsapp' === $filter ? ' button-primary' : '' ) . '" href="' . esc_url( $base . '&event=whatsapp' ) . '">واتساب</a>';
	echo '</p>';
	echo '<table class="widefat striped"><thead><tr>';
	echo '<th>الوقت</th><th>الحدث</th><th>عنوان IP</th><th>الجهاز</th><th>الصفحة</th><th>المصدر</th>';
	echo '</tr></thead><tbody>';
	if ( ! $rows ) {
		echo '<tr><td colspan="6">لا توجد زيارات بعد. افتح صفحة الإعلانات ثم ارجع هنا.</td></tr>';
	}
	foreach ( (array) $rows as $row ) {
		echo '<tr>';
		echo '<td>' . esc_html( $row->created_at ) . '</td>';
		echo '<td>' . esc_html( maxart_ads_event_label( $row->event ) ) . '</td>';
		echo '<td><code>' . esc_html( $row->ip ) . '</code></td>';
		echo '<td>' . esc_html( $row->device_label ) . '<br /><small>' . esc_html( $row->device_id ) . '</small></td>';
		echo '<td>' . esc_html( $row->page ) . '</td>';
		echo '<td>' . esc_html( $row->referrer ) . ( $row->utm ? '<br />UTM: ' . esc_html( $row->utm ) : '' ) . '</td>';
		echo '</tr>';
	}
	echo '</tbody></table></div>';
}

function maxart_ads_ensure_page() {
	if ( get_page_by_path( 'ads' ) ) {
		return;
	}
	wp_insert_post(
		array(
			'post_title'   => 'كشف تسربات المياه وعزل الأسطح',
			'post_name'    => 'ads',
			'post_status'  => 'publish',
			'post_type'    => 'page',
			'post_content' => 'صفحة إعلانات كشف تسربات المياه وعزل الأسطح في الإمارات.',
		),
		true
	);
}
add_action( 'init', 'maxart_ads_ensure_page', 20 );
