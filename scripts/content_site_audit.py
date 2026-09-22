#!/usr/bin/env python3
"""Live content+site audit for max-art-ae.com, excluding theme internals."""

from __future__ import annotations

import html as htmlmod
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import cli, config, request  # noqa: E402
from wp_connect import USER_AGENT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "content-site-audit-data.json"
UA_BROWSER = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)

IDENTITY_NEEDLES = (
    "97431110184",
    "97431553076",
    "+974",
    "خالد المطيري",
    "ركن التطور",
    "rukn",
    "ISO 9001",
    "0500000000",
    "34 خدمة",
    "5415",
    "{{mpg",
    "lorem ipsum",
    "Suggested text",
    "م. فريق",
)
PHONE_OK = "971544437175"
PHONE_DISPLAY = "0544437175"

AR_WORD = re.compile(r"[\u0600-\u06FFA-Za-z0-9]+")
TAG_RE = re.compile(r"<[^>]+>")
SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)


def http_probe(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA_BROWSER, "Accept": "text/html,application/json,*/*;q=0.8"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read(8000)
            return {
                "url": url,
                "status": int(resp.status),
                "final": resp.geturl(),
                "ctype": (resp.headers.get("Content-Type") or "")[:80],
                "bytes": int(resp.headers.get("Content-Length") or len(body)),
                "robots": (resp.headers.get("X-Robots-Tag") or "")[:120],
                "snippet": body.decode("utf-8", "replace")[:180].replace("\n", " "),
            }
    except urllib.error.HTTPError as exc:
        snippet = exc.read(180).decode("utf-8", "replace").replace("\n", " ")
        return {"url": url, "status": exc.code, "final": url, "snippet": snippet[:180]}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status": 0, "error": str(exc)[:180]}


def rest_list(url, user, password, path: str, extra: str = "") -> list:
    items: list = []
    page = 1
    while page <= 20:
        q = f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}&context=edit{extra}"
        try:
            data = request(f"{url}/wp-json{q}", user, password, timeout=90)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "HTTP 400" in msg or "HTTP 404" in msg:
                break
            raise
        if not data:
            break
        if isinstance(data, dict):
            data = data.get("items") or []
        if not isinstance(data, list) or not data:
            break
        items.extend(data)
        if len(data) < 100:
            break
        page += 1
    return items


def strip_html(raw: str) -> str:
    text = SCRIPT_RE.sub(" ", raw or "")
    text = TAG_RE.sub(" ", text)
    text = htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def words(text: str) -> int:
    return len(AR_WORD.findall(text or ""))


def main() -> int:
    url, user, password = config()
    report: dict = {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "scope": "content+site excluding theme internals",
    }

    info = request(f"{url}/wp-json/wpvibe/v1/site-info", user, password)
    report["site"] = {
        "name": (info or {}).get("site_name"),
        "wp": (info or {}).get("wp_version"),
        "php": (info or {}).get("php_version"),
        "wpvibe": (info or {}).get("wpvibe_plugin_version"),
        "theme_name": ((info or {}).get("active_theme") or {}).get("name"),
        "theme_note": "template internals excluded from this audit",
    }

    report["plugins"] = json.loads(
        cli(url, user, password, "plugin list --fields=name,status,version --format=json").get("stdout") or "[]"
    )
    report["users"] = json.loads(
        cli(url, user, password, "user list --fields=ID,user_login,display_name,roles,user_email --format=json").get("stdout")
        or "[]"
    )
    report["menus"] = json.loads(cli(url, user, password, "menu list --format=json").get("stdout") or "[]")

    options = {}
    for key in (
        "blogname",
        "blogdescription",
        "posts_per_page",
        "show_on_front",
        "page_on_front",
        "page_for_posts",
        "permalink_structure",
        "timezone_string",
        "date_format",
        "WPLANG",
        "blog_public",
        "facebook",
        "instagram",
        "twitter",
        "youtube",
        "linkedin",
        "tiktok",
        "whatsapp",
        "phone",
        "mobile",
        "email",
        "address",
        "rank_math_webmaster",
        "rank_math_google_analytic_options",
        "rank_math_modules",
        "rank_math_robots_txt_content",
        "rank_math_sitemap",
        "rank_math_titles",
        "litespeed.conf.cache",
        "litespeed.conf.cache-priv",
        "litespeed.conf.optm-css_min",
        "litespeed.conf.optm-js_min",
        "litespeed.conf.optm-css_comb",
        "litespeed.conf.optm-js_comb",
    ):
        data = cli(url, user, password, f"option get {key}")
        options[key] = {
            "exit": data.get("exit_code"),
            "out": ((data.get("stdout") or "").strip()[:500]),
            "err": ((data.get("stderr") or "").strip()[:200]),
        }
    report["options"] = options

    type_routes = {
        "post": "/wp/v2/posts",
        "page": "/wp/v2/pages",
        "services": "/wp/v2/services",
        "reviews": "/wp/v2/reviews",
        "faqs": "/wp/v2/faqs",
        "pricing": "/wp/v2/pricing",
        "portfolio": "/wp/v2/portfolio",
        "before_after": "/wp/v2/before_after",
    }
    types = tuple(type_routes)
    counts = {}
    for t in types:
        raw = cli(
            url,
            user,
            password,
            f"post list --post_type={t} --post_status=publish --format=count --posts_per_page=1",
        ).get("stdout") or "0"
        try:
            counts[t] = int(str(raw).strip().split()[-1])
        except ValueError:
            counts[t] = str(raw).strip()[:80]
        for st in ("draft", "private", "pending", "trash"):
            raw2 = cli(
                url,
                user,
                password,
                f"post list --post_type={t} --post_status={st} --format=count --posts_per_page=1",
            ).get("stdout") or "0"
            try:
                counts[f"{t}:{st}"] = int(str(raw2).strip().split()[-1])
            except ValueError:
                counts[f"{t}:{st}"] = str(raw2).strip()[:80]
    report["counts"] = counts

    fields = "id,link,slug,status,type,date,modified,featured_media,title,excerpt"
    items = []
    leftovers = defaultdict(list)
    word_stats = []
    featured = Counter()
    dates = Counter()
    titles = []
    noindexish = []
    thin = []
    missing_feat = []
    ld_json = 0

    for t, route in type_routes.items():
        try:
            rows = rest_list(
                url,
                user,
                password,
                route,
                extra="&_fields=" + fields,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"skip {t}: {str(exc)[:160]}")
            continue
        print(f"fetched {t} {len(rows)}")
        for row in rows:
            title = (row.get("title") or {}).get("rendered") or (row.get("title") or {}).get("raw") or ""
            title = htmlmod.unescape(TAG_RE.sub("", title)).strip()
            excerpt = (row.get("excerpt") or {}).get("rendered") or (row.get("excerpt") or {}).get("raw") or ""
            content = (row.get("content") or {}).get("raw") or (row.get("content") or {}).get("rendered") or ""
            text = strip_html(content)
            wc = words(text)
            fm = int(row.get("featured_media") or 0)
            featured[fm] += 1
            day = (row.get("date") or "")[:10]
            dates[day] += 1
            blob = " ".join([title, excerpt, content, text])
            hits = [n for n in IDENTITY_NEEDLES if n.lower() in blob.lower()]
            if "application/ld+json" in content:
                ld_json += 1
            rec = {
                "id": row.get("id"),
                "type": t,
                "status": row.get("status"),
                "link": row.get("link"),
                "slug": row.get("slug"),
                "title": title,
                "date": row.get("date"),
                "modified": row.get("modified"),
                "featured_media": fm,
                "words": wc,
                "hits": hits,
                "has_h2": bool(re.search(r"<h2\b", content, re.I)),
                "ld_json": "application/ld+json" in content,
            }
            items.append(rec)
            titles.append((title, rec["id"], rec["link"]))
            if wc < 400:
                thin.append(rec)
            if fm == 0:
                missing_feat.append(rec)
            for h in hits:
                leftovers[h].append({"id": rec["id"], "title": title, "link": rec["link"]})

    report["item_count"] = len(items)
    report["ld_json_in_body"] = ld_json
    report["thin_under_400"] = len(thin)
    report["no_featured"] = len(missing_feat)
    report["featured_top"] = featured.most_common(8)
    report["dates_top"] = dates.most_common(8)
    report["leftovers"] = {k: v[:15] + ([{"more": len(v) - 15}] if len(v) > 15 else []) for k, v in leftovers.items()}
    report["leftover_counts"] = {k: len(v) for k, v in leftovers.items()}

    sql_leftovers = {}
    for needle in IDENTITY_NEEDLES:
        safe = needle.replace("'", "''").replace("\\", "\\\\")
        q = cli(
            url,
            user,
            password,
            f"""db query "SELECT ID, post_type, post_status, post_title FROM wp_posts WHERE post_status IN ('publish','draft','private') AND (post_content LIKE '%{safe}%' OR post_title LIKE '%{safe}%' OR post_excerpt LIKE '%{safe}%') LIMIT 25" --limit=30""",
        )
        sql_leftovers[needle] = {"out": (q.get("stdout") or "")[:2500], "err": (q.get("stderr") or "")[:200]}
    report["sql_leftovers"] = sql_leftovers

    report["sql_lengths"] = {
        "out": (
            cli(
                url,
                user,
                password,
                """db query "SELECT post_type, COUNT(*) n, ROUND(AVG(CHAR_LENGTH(post_content))) avg_len, SUM(CHAR_LENGTH(post_content)<1500) short_1500, SUM(CHAR_LENGTH(post_content)<4000) short_4000 FROM wp_posts WHERE post_status='publish' AND post_type IN ('post','page','services','reviews','faqs','pricing','portfolio','before_after') GROUP BY post_type" --limit=20""",
            ).get("stdout")
            or ""
        )[:2000]
    }
    report["sql_noindex"] = {
        "out": (
            cli(
                url,
                user,
                password,
                """db query "SELECT COUNT(*) c FROM wp_postmeta pm INNER JOIN wp_posts p ON p.ID=pm.post_id WHERE pm.meta_key='rank_math_robots' AND pm.meta_value LIKE '%noindex%' AND p.post_status='publish'" --limit=5""",
            ).get("stdout")
            or ""
        )[:500]
    }
    report["sql_ldjson"] = {
        "out": (
            cli(
                url,
                user,
                password,
                """db query "SELECT COUNT(*) c FROM wp_posts WHERE post_status='publish' AND post_content LIKE '%application/ld+json%'" --limit=5""",
            ).get("stdout")
            or ""
        )[:400]
    }
    report["sql_featured"] = {
        "out": (
            cli(
                url,
                user,
                password,
                """db query "SELECT meta_value img, COUNT(*) c FROM wp_postmeta pm INNER JOIN wp_posts p ON p.ID=pm.post_id WHERE pm.meta_key='_thumbnail_id' AND p.post_status='publish' GROUP BY meta_value ORDER BY c DESC LIMIT 10" --limit=15""",
            ).get("stdout")
            or ""
        )[:1500]
    }
    report["sql_dates"] = {
        "out": (
            cli(
                url,
                user,
                password,
                """db query "SELECT DATE(post_date) d, COUNT(*) c FROM wp_posts WHERE post_status='publish' AND post_type='post' GROUP BY DATE(post_date) ORDER BY c DESC LIMIT 10" --limit=15""",
            ).get("stdout")
            or ""
        )[:800]
    }
    report["thin_samples"] = [
        {"id": x["id"], "type": x["type"], "title": x["title"], "words": x["words"], "link": x["link"]}
        for x in sorted(thin, key=lambda r: r["words"])[:40]
    ]
    report["items_by_type_words"] = {}
    by_type = defaultdict(list)
    for rec in items:
        by_type[rec["type"]].append(rec["words"])
    for t, wlist in by_type.items():
        report["items_by_type_words"][t] = {
            "n": len(wlist),
            "avg": round(sum(wlist) / max(len(wlist), 1)),
            "min": min(wlist) if wlist else 0,
            "max": max(wlist) if wlist else 0,
            "under400": sum(1 for w in wlist if w < 400),
            "under1000": sum(1 for w in wlist if w < 1000),
        }

    # duplicate titles
    title_map = defaultdict(list)
    for title, pid, link in titles:
        title_map[title].append({"id": pid, "link": link})
    report["duplicate_titles"] = {k: v for k, v in title_map.items() if k and len(v) > 1}

    # taxonomies
    tax = {}
    for name in ("category", "post_tag", "cities", "service_categories"):
        data = cli(url, user, password, f"term list {name} --number=200")
        tax[name] = (data.get("stdout") or "")[:4000]
    report["taxonomies_raw"] = tax

    # Rank Math robots on sample posts
    robot_samples = []
    sample_ids = [x["id"] for x in items if x["type"] == "post"][:12]
    pillars = [x["id"] for x in items if x["type"] in ("page", "services")]
    for pid in sample_ids + pillars[:20]:
        meta = cli(url, user, password, f"post meta get {pid} rank_math_robots --format=json")
        canon = cli(url, user, password, f"post meta get {pid} rank_math_canonical")
        robot_samples.append(
            {
                "id": pid,
                "robots": (meta.get("stdout") or "").strip()[:200],
                "canonical": (canon.get("stdout") or "").strip()[:200],
            }
        )
    report["rank_math_samples"] = robot_samples

    noindex_count = 0
    indexed_pseo = 0
    # Count noindex via db query if allowed
    q = cli(
        url,
        user,
        password,
        r"""db query "SELECT COUNT(*) c FROM wp_postmeta WHERE meta_key='rank_math_robots' AND meta_value LIKE '%noindex%'" --limit=5""",
    )
    report["noindex_query"] = {"out": (q.get("stdout") or "")[:500], "err": (q.get("stderr") or "")[:300]}

    # Public probes
    paths = [
        "/",
        "/robots.txt",
        "/sitemap_index.xml",
        "/sitemap.xml",
        "/mpg-sitemap-plumbing-services.xml",
        "/page-sitemap.xml",
        "/post-sitemap.xml",
        "/services-sitemap.xml",
        "/about-us/",
        "/contact-us/",
        "/privacy-policy/",
        "/blog/",
        "/services/",
        "/services/leak-detection/",
        "/services/roof-insulation/",
        "/reviews/",
        "/faqs/",
        "/pricing/",
        "/portfolio/",
        "/before-after/",
        "/author/admin/",
        "/author/mahmoud/",
        "/en/",
        "/sa/",
        "/qa/",
        "/mpg_citys-expert-plumbing-services/",
        "/this-page-does-not-exist-audit-404/",
        "/wp-login.php",
        "/feed/",
        "/comments/feed/",
        "/?s=تسرب",
    ]
    report["probes"] = [http_probe(url + p) for p in paths]

    # homepage HTML identity + popup + claims
    home = request(f"{url}/wp-json/wpvibe/v1/rendered-html", user, password, method="POST", payload={"path": "/"})
    html = (home or {}).get("html") or ""
    report["homepage"] = {
        "html_len": len(html),
        "promo": "maxart-promo" in html,
        "promo_delay_3000": "},3000)" in html,
        "win_ae": "win-ae.webp" in html,
        "reffpa": "reffpa.com" in html,
        "phone_ok": PHONE_OK in html or PHONE_DISPLAY in html or "0544437175" in html,
        "phone_qatar": "97431110184" in html or "+974" in html,
        "rukn": "ركن التطور" in html or "rukn" in html.lower(),
        "claim_34": "34" in html and "خدم" in html,
        "claim_5415": "5415" in html or "5,415" in html,
        "og_site": bool(re.search(r'property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)', html)),
        "ld_json_count": html.lower().count("application/ld+json"),
        "title": (re.search(r"<title>(.*?)</title>", html, re.I | re.S).group(1)[:180] if re.search(r"<title>", html, re.I) else ""),
        "h1": re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)[:5],
        "tel_links": re.findall(r'href=["\'](tel:[^"\']+)["\']', html)[:10],
        "wa_links": re.findall(r'href=["\'](https?://wa\.me/[^"\']+)["\']', html)[:10],
        "social_links": re.findall(r'href=["\'](https?://(?:www\.)?(?:facebook|instagram|twitter|x|youtube|tiktok|linkedin)\.[^"\']+)["\']', html, re.I)[:15],
        "mpg": "{{mpg" in html,
    }

    # comments
    report["comments"] = {
        "all": (cli(url, user, password, "comment count").get("stdout") or "").strip()[:200],
    }

    # media count
    report["media"] = (cli(url, user, password, "media list --posts_per_page=1 --format=count").get("stdout") or "").strip()[:80]

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT, "items", len(items), "leftovers", report["leftover_counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
