<?php
/**
 * Snippet appended to kayan-theme/functions.php on the live site.
 * Re-apply via WPVibe file/edit if a draft-theme publish overwrites it.
 */

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
		echo '<link rel="stylesheet" href="' . esc_url( $href . '?ver=' . rawurlencode( $ver ) ) . '" media="all" />' . "\n";
	}
}
add_action( 'admin_head', 'maxart_print_core_admin_css', 1 );
add_action( 'login_head', 'maxart_print_core_admin_css', 1 );

add_action( 'init', 'maxart_redirect_foreign_prefixes', 1 );
add_action( 'template_redirect', 'maxart_redirect_foreign_prefixes', -1 );
function maxart_redirect_foreign_prefixes() {
	if ( is_admin() ) {
		return;
	}
	$path  = trim( (string) parse_url( $_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH ), '/' );
	$first = strtolower( explode( '/', $path )[0] ?? '' );
	$lang  = strtolower( (string) get_query_var( 'kayan_lang' ) );
	if ( $lang === 'en' || in_array( $first, array( 'en', 'sa', 'qa', 'kw', 'om', 'bh', 'eg' ), true ) ) {
		wp_safe_redirect( home_url( '/' ), 301 );
		exit;
	}
}

add_action( 'wp_head', 'maxart_hide_country_switcher', 99 );
function maxart_hide_country_switcher() {
	echo '<style id="maxart-fixes">[id^="kayanSwitcher"]{display:none!important}.kayan-service-body,.kayan-service-body *{color:#1e2a4a!important}.kayan-service-body a{color:#0b57d0!important}.kayan-service-body h2{margin:1.2em 0 .4em;font-size:1.25em}</style>';
	if ( is_front_page() || is_home() ) {
		echo '<meta property="og:image" content="https://max-art-ae.com/wp-content/uploads/2026/07/1783747619594.webp" />';
		echo '<meta name="twitter:image" content="https://max-art-ae.com/wp-content/uploads/2026/07/1783747619594.webp" />';
	}
}

add_action( 'wp_footer', 'maxart_section_ids', 99 );
function maxart_section_ids() {
	echo '<script>document.querySelectorAll("h2").forEach(function(h){var t=h.textContent||"";var id="";if(t.indexOf("ما الخدمة")!==-1)id="services";else if(t.indexOf("نغطي")!==-1)id="areas";else if(t.indexOf("مقالات")!==-1)id="blog";else if(t.indexOf("لماذا")!==-1||t.indexOf("من نحن")!==-1)id="why";else if(t.indexOf("الأسئلة")!==-1)id="faq";else if(t.indexOf("مشروع")!==-1||t.indexOf("أعمال")!==-1)id="projects";if(id){var s=h.parentElement;if(s&&!s.id)s.id=id;if(!h.id)h.id=id+"-heading";}});</script>';
}

add_filter( 'robots_txt', 'maxart_robots_txt', 99, 2 );
function maxart_robots_txt( $output, $public ) {
	return "User-agent: *\nAllow: /\n\nSitemap: https://max-art-ae.com/sitemap_index.xml\n";
}

add_filter( 'get_post_metadata', 'maxart_sanitize_widget_claims', 10, 4 );
function maxart_sanitize_widget_claims( $value, $object_id, $meta_key, $single ) {
	if ( 'widget_post_meta' !== $meta_key ) {
		return $value;
	}
	if ( ! in_array( (int) $object_id, array( 3592, 3593, 3594, 3595, 3596 ), true ) ) {
		return $value;
	}
	static $busy = false;
	if ( $busy ) {
		return $value;
	}
	$busy = true;
	$meta = get_post_meta( $object_id, $meta_key, true );
	$busy = false;
	if ( ! is_array( $meta ) ) {
		return $value;
	}
	$walker = function ( &$node ) use ( &$walker ) {
		if ( ! is_array( $node ) ) {
			return;
		}
		foreach ( $node as &$child ) {
			$walker( $child );
		}
		unset( $child );
		if ( isset( $node['number'] ) && (string) $node['number'] === '34' ) {
			$node['number'] = '10';
		}
		if ( isset( $node['number'] ) && (string) $node['number'] === '5415' ) {
			$node['number'] = '10';
			$node['suffix'] = '';
			$node['label']  = 'خدمات معلنة';
		}
		foreach ( array( 'title', 'desc', 'content', 'small', 'us_text', 'label' ) as $field ) {
			if ( ! empty( $node[ $field ] ) && is_string( $node[ $field ] ) ) {
				$node[ $field ] = str_replace( '34 خدمة', 'خدماتنا', $node[ $field ] );
			}
		}
	};
	$walker( $meta );
	return array( $meta );
}

add_action( 'wp_footer', 'maxart_promo_popup', 100 );
function maxart_promo_popup() {
	if ( is_admin() ) {
		return;
	}
	$img  = esc_url( 'https://max-art-ae.com/wp-content/uploads/2026/09/win-ae.webp' );
	$href = esc_url( 'https://reffpa.com/L?tag=d_6118963m_70865c_ae1&site=6118963&ad=70865' );
	echo '<style id="maxart-promo-css">#maxart-promo{position:fixed;inset:0;z-index:2147483000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.58);padding:18px;box-sizing:border-box}#maxart-promo[hidden]{display:none!important}#maxart-promo .maxart-promo-card{position:relative;max-width:min(640px,94vw);width:100%;border-radius:18px;overflow:visible;box-shadow:0 18px 50px rgba(0,0,0,.45)}#maxart-promo a{display:block;line-height:0;border-radius:18px;overflow:hidden;background:#0b1d3a}#maxart-promo img{display:block;width:100%;height:auto}#maxart-promo .maxart-promo-close{position:absolute;top:-12px;left:-12px;width:38px;height:38px;border:0;border-radius:50%;background:#fff;color:#111;font-size:28px;line-height:38px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.3);z-index:2}#maxart-promo .maxart-promo-close:focus{outline:2px solid #fff;outline-offset:2px}@media(max-width:600px){#maxart-promo{align-items:flex-end;padding:12px}#maxart-promo .maxart-promo-card{max-width:100%}#maxart-promo .maxart-promo-close{top:8px;left:8px}}</style>';
	echo '<div id="maxart-promo" hidden role="dialog" aria-modal="true" aria-label="إعلان">';
	echo '<div class="maxart-promo-card">';
	echo '<button type="button" class="maxart-promo-close" aria-label="إغلاق">&times;</button>';
	echo '<a class="maxart-promo-link" href="' . $href . '" target="_blank" rel="sponsored noopener">';
	echo '<img src="' . $img . '" alt="إعلان" width="1364" height="768" loading="eager">';
	echo '</a></div></div>';
	echo '<script>(function(){var k="maxart-promo-closed";var el=document.getElementById("maxart-promo");if(!el)return;if(sessionStorage.getItem(k))return;function closePromo(){el.setAttribute("hidden","");try{sessionStorage.setItem(k,"1")}catch(e){}}var btn=el.querySelector(".maxart-promo-close");if(btn)btn.addEventListener("click",function(e){e.preventDefault();e.stopPropagation();closePromo()});el.addEventListener("click",function(e){if(e.target===el)closePromo()});document.addEventListener("keydown",function(e){if(e.key==="Escape")closePromo()});setTimeout(function(){el.removeAttribute("hidden")},700)})();</script>';
}
