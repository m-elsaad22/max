#!/usr/bin/env python3
"""Technical SEO + content-quality audit for published WordPress items.

Fetches posts/pages/CPTs from the live REST API (credentials via .env),
then writes CSV + Markdown reports under site/.

Stdlib only. Arabic-aware whitespace word counts, heading extraction,
template/boilerplate fingerprints, shingle similarity, and intent checks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html as htmlmod
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wp_connect import USER_AGENT, config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "site"
THIN_WORDS = 1000
NEAR_DUP_THRESHOLD = 0.78
CANNIBAL_MIN_GROUP = 3
TYPES = ("post", "page", "services", "reviews", "faqs", "pricing", "portfolio", "before_after")

AR_STOP = {
    "في", "من", "على", "إلى", "الى", "عن", "مع", "هذا", "هذه", "ذلك", "تلك",
    "التي", "الذي", "أو", "او", "و", "ثم", "قد", "كان", "كانت", "يكون",
    "ما", "لا", "لم", "لن", "إن", "ان", "أن", "ان", "كل", "كما", "بعد",
    "قبل", "بين", "حتى", "هناك", "هنا", "أيضا", "ايضا", "جدا", "حيث",
    "شركة", "الشركات", "خدمة", "خدمات", "أفضل", "افضل", "أفضل",
}

PLACE_RE = re.compile(
    r"النعيمية|الرويس|الحميدية|الجرف|المويهات|الراشدية|المويهات|"
    r"الشارقة|دبي|عجمان|أبوظبي|ابوظبي|العين|الفجيرة|رأس الخيمة|ام القيوين|"
    r"أم القيوين|خورفكان|دبا|القصيص|ديرة|بر دبي|جميرا|الممزر|النهدة|"
    r"المجاز|الخان|المجاز|الصجعة|محيصنة|القوز|البرشاء|جبل علي|الورقاء|"
    r"الميناء|الحمرية|الذيد|كلباء|مسافي|ليوا|الظفرة|مدينة زايد|"
    r"البطين|الخالدية|الكرامة|الروضة|المويهات|اليلايس|مصفوت|"
    r"[A-Za-z]{3,}",
    re.I,
)

BOILER_PHRASES = (
    "كتب هذا المقال",
    "آخر تحديث",
    "مراجعة:",
    "فريق ماكس آرت",
    "هي خدمة متخصصة تُقدّمها",
    "باستخدام أحدث الأجهزة والمعدات",
    "وصول سريع خلال ساعتين",
    "نتائج مضمونة مع ضمان مكتوب",
    "فريق متخصص مؤهل ومدرَّب",
    "استخدام مواد آمنة صديقة للبيئة",
    "نصيحة الخبير:",
    "كل ما تحتاج معرفته عن",
    "مع ارتفاع الطلب على خدمات",
    "أصبح الاختيار الصحيح للشركة",
    '"@type": "LocalBusiness"',
    '"telephone": "+971',
    "جدول الأسعار",
    "الأسئلة الشائعة",
)

PLACEHOLDER_RE = re.compile(
    r"lorem ipsum|dummy text|placeholder|coming soon|\btbd\b|\btodo\b|"
    r"\[اكتب|\[insert|\{\{[a-z_]+\}|\bxxx+\b",
    re.I,
)

TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("كشف/إصلاح تسربات", ("تسرب", "تسريب", "كشف تسرب", "رطوبة", "عزل مائي")),
    ("عزل أسطح", ("عزل", "سطح", "أسطح", "حراري")),
    ("ورق جدران", ("ورق الجدران", "ورق جدران", "wallpaper")),
    ("مظلات وسواتر", ("مظلات", "مظلة", "سواتر", "ساتر", "برجولات", "برجولة")),
    ("حدادة", ("حدادة", "حداد", "حديد", "مشغول", "بوابة", "درابزين")),
    ("دهانات/صبغ", ("دهان", "دهانات", "صبغ", "طلاء")),
    ("جبس بورد", ("جبس", "جبسبورد", "جبس بورد")),
    ("سباكة", ("سباكة", "سباك", "تمديدات", "مواسير")),
    ("كهرباء", ("كهرباء", "كهربائي", "تمديدات كهرب")),
    ("صيانة عامة", ("صيانة", "ترميم", "تشطيب")),
]


def request_json(
    url: str,
    user: str,
    password: str,
    timeout: int = 90,
) -> tuple[Any, dict[str, str]]:
    import base64

    last: Exception | None = None
    headers = {
        "Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode(),
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    for attempt in range(6):
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                hdrs = {k.lower(): v for k, v in response.headers.items()}
                data = json.loads(raw.decode("utf-8")) if raw else None
                return data, hdrs
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404):
                raise
            last = exc
            time.sleep(1.3 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.3 * (attempt + 1))
    raise RuntimeError(f"GET failed {url}: {last}") from last


def fetch_type(base: str, user: str, password: str, rest_base: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        q = urllib.parse.urlencode(
            {
                "per_page": 50,
                "page": page,
                "status": "publish",
                "context": "view",
            }
        )
        url = f"{base}/wp-json/wp/v2/{rest_base}?{q}"
        try:
            data, hdrs = request_json(url, user, password)
        except urllib.error.HTTPError as exc:
            if exc.code in (400, 404) or page > 1:
                break
            raise
        if not data:
            break
        if isinstance(data, dict) and data.get("code"):
            break
        batch = data if isinstance(data, list) else []
        items.extend(batch)
        total_pages = int(hdrs.get("x-wp-totalpages") or "1")
        print(f"  {rest_base} page {page}/{total_pages} (+{len(batch)})", flush=True)
        if page >= total_pages or len(batch) < 50:
            break
        page += 1
        time.sleep(0.15)
    return items


def strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw or "")
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</p>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = htmlmod.unescape(text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)  # Arabic diacritics
    text = re.sub(r"[ـ]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def headings(html: str) -> dict[str, list[str]]:
    out = {"h1": [], "h2": [], "h3": []}
    for level in ("h1", "h2", "h3"):
        for m in re.finditer(rf"(?is)<{level}[^>]*>(.*?)</{level}>", html or ""):
            t = strip_html(m.group(1))
            if t:
                out[level].append(t)
    return out


def word_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9\u0600-\u06FF]+", text) if t]


def normalize_places(text: str) -> str:
    return PLACE_RE.sub("{LOC}", text)


def skeleton(h2s: list[str]) -> str:
    parts = [normalize_places(h).strip() for h in h2s]
    parts = [p for p in parts if p]
    return " | ".join(parts[:12])


def shingles(tokens: list[str], n: int = 5) -> set[int]:
    if len(tokens) < n:
        joined = " ".join(tokens)
        return {int(hashlib.md5(joined.encode("utf-8")).hexdigest()[:12], 16)} if joined else set()
    out: set[int] = set()
    for i in range(0, min(len(tokens) - n + 1, 400)):
        gram = " ".join(tokens[i : i + n])
        out.add(int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:12], 16))
    return out


def jaccard(a: set[int], b: set[int]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def detect_topics(text: str) -> list[tuple[str, int]]:
    scored: list[tuple[str, int]] = []
    for name, kws in TOPIC_RULES:
        score = sum(text.count(k) for k in kws)
        if score:
            scored.append((name, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def title_topic(title: str) -> str | None:
    hits = detect_topics(title)
    return hits[0][0] if hits else None


def body_topic(text: str) -> str | None:
    hits = detect_topics(text)
    return hits[0][0] if hits else None


def cannibal_key(title: str) -> str:
    t = normalize_places(title)
    t = re.sub(r"شركة|افضل|أفضل|دليل|اسعار|أسعار|2026|2025", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:80]


def analyze_item(item: dict[str, Any]) -> dict[str, Any]:
    html = (item.get("content") or {}).get("rendered") or ""
    title = strip_html((item.get("title") or {}).get("rendered") or "")
    excerpt = strip_html((item.get("excerpt") or {}).get("rendered") or "")
    text = strip_html(html)
    tokens = word_tokens(text)
    heads = headings(html)
    skel = skeleton(heads["h2"])
    boiler_hits = [p for p in BOILER_PHRASES if p in html or p in text]
    ph = PLACEHOLDER_RE.findall(html + "\n" + title)
    t_topic = title_topic(title)
    b_topic = body_topic(text)
    loc_in_title = PLACE_RE.findall(title)
    loc_missing = []
    for loc in loc_in_title:
        if loc.isascii():
            continue
        if loc and loc not in text and "{LOC}" not in loc:
            loc_missing.append(loc)

    issues: list[str] = []
    notes: list[str] = []
    wc = len(tokens)

    if wc < THIN_WORDS:
        issues.append("thin_content")
        notes.append(f"عدد الكلمات {wc} < {THIN_WORDS}")

    if wc < 300:
        issues.append("very_thin")
        notes.append("محتوى قصير جداً (<300 كلمة)")

    if len(boiler_hits) >= 4:
        issues.append("boilerplate")
        notes.append("عبارات نمطية: " + "؛ ".join(boiler_hits[:6]))

    if ph:
        issues.append("placeholder")
        notes.append("نصوص مؤقتة: " + ", ".join(sorted(set(ph))[:5]))

    if not heads["h1"]:
        notes.append("لا H1 داخل جسم المقالة (ووردبريس عادةً يعرض العنوان كـ H1 من القالب)")
        issues.append("no_content_h1")

    if len(heads["h2"]) < 2:
        issues.append("missing_h2")
        notes.append(f"عدد H2 = {len(heads['h2'])}")

    if len(heads["h3"]) == 0 and wc >= 800:
        issues.append("missing_h3")
        notes.append("لا توجد H3 رغم طول المحتوى")

    if t_topic and b_topic and t_topic != b_topic:
        issues.append("intent_mismatch")
        notes.append(f"العنوان عن «{t_topic}» بينما المتن يغلب عليه «{b_topic}»")

    if t_topic:
        # title keyword barely in body
        title_kws = [w for w in word_tokens(t_topic) if len(w) > 2]
        if title_kws:
            dens = sum(text.count(w) for w in title_kws)
            if dens < 2 and wc > 200:
                issues.append("intent_mismatch")
                notes.append("كلمات موضوع العنوان شبه غائبة عن المتن")

    if loc_missing:
        issues.append("intent_mismatch")
        notes.append("الموقع في العنوان غير مذكور في المتن: " + "، ".join(loc_missing[:4]))

    if not excerpt or len(word_tokens(excerpt)) < 12:
        issues.append("missing_excerpt")
        notes.append("مقتطف فارغ أو قصير")

    if not item.get("featured_media"):
        issues.append("missing_featured_image")
        notes.append("لا توجد صورة بارزة")

    # structural oddities
    if html.count("<table") > 3:
        notes.append("جداول متعددة (غالباً قالب أسعار مكرر)")
    if '"@type"' in html and html.count("LocalBusiness") >= 1:
        notes.append("Schema JSON-LD مضمّن داخل المحتوى")
        issues.append("boilerplate")

    norm_tokens = word_tokens(normalize_places(text))
    return {
        "id": item.get("id"),
        "type": item.get("type"),
        "title": title,
        "url": item.get("link") or "",
        "date": (item.get("date") or "")[:10],
        "word_count": wc,
        "h1_count": len(heads["h1"]),
        "h2_count": len(heads["h2"]),
        "h3_count": len(heads["h3"]),
        "h2_skeleton": skel,
        "boilerplate_hits": len(boiler_hits),
        "featured_media": item.get("featured_media") or 0,
        "title_topic": t_topic or "",
        "body_topic": b_topic or "",
        "cannibal_key": cannibal_key(title),
        "shingles": shingles([t for t in norm_tokens if t not in AR_STOP and len(t) > 1]),
        "issues": issues,
        "notes": notes,
        "excerpt_words": len(word_tokens(excerpt)),
    }


def cluster_near_dupes(rows: list[dict[str, Any]]) -> dict[int, list[int]]:
    """Greedy clusters of near-duplicate bodies. Returns id -> cluster member ids."""
    posts = [r for r in rows if r["type"] == "post" and r["shingles"]]
    parent: dict[int, int] = {r["id"]: r["id"] for r in posts}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # Compare each to next 40 by id order (same-day pSEO batches are sequential)
    posts_sorted = sorted(posts, key=lambda r: r["id"])
    for i, a in enumerate(posts_sorted):
        for b in posts_sorted[i + 1 : i + 45]:
            sim = jaccard(a["shingles"], b["shingles"])
            if sim >= NEAR_DUP_THRESHOLD:
                union(a["id"], b["id"])
    clusters: dict[int, list[int]] = defaultdict(list)
    for r in posts:
        clusters[find(r["id"])].append(r["id"])
    return {k: v for k, v in clusters.items() if len(v) >= 2}


def issue_label(code: str) -> str:
    return {
        "thin_content": "محتوى ضعيف (<1000 كلمة)",
        "very_thin": "محتوى ضعيف جداً",
        "boilerplate": "قالب/نصوص نمطية",
        "near_duplicate": "محتوى مكرر/متشابه",
        "cannibalization": "تآكل كلمات مفتاحية",
        "intent_mismatch": "عدم توافق نية البحث",
        "no_content_h1": "لا H1 في جسم المحتوى",
        "missing_h2": "نقص H2",
        "missing_h3": "نقص H3",
        "placeholder": "نص مؤقت/غير مكتمل",
        "missing_excerpt": "مقتطف ناقص",
        "missing_featured_image": "صورة بارزة مفقودة",
        "shared_featured_image": "صورة بارزة مكررة على نطاق واسع",
    }.get(code, code)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "id",
        "type",
        "title",
        "url",
        "date",
        "word_count",
        "h1_count",
        "h2_count",
        "h3_count",
        "title_topic",
        "body_topic",
        "boilerplate_hits",
        "featured_media",
        "issues",
        "notes",
        "duplicate_group",
        "cannibal_group",
        "h2_skeleton",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    **{k: r.get(k, "") for k in fields},
                    "issues": " | ".join(issue_label(i) for i in r.get("issues") or []),
                    "notes": "؛ ".join(r.get("notes") or []),
                    "duplicate_group": r.get("duplicate_group") or "",
                    "cannibal_group": r.get("cannibal_group") or "",
                }
            )


def md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def write_markdown(
    path: Path,
    rows: list[dict[str, Any]],
    stats: dict[str, Any],
) -> None:
    lines: list[str] = []
    lines.append("# تدقيق محتوى وSEO تقني — max-art-ae.com")
    lines.append("")
    lines.append(f"**تاريخ المسح:** {stats['scanned_at']}")
    lines.append(f"**العناصر المنشورة المفحوصة:** {stats['total']}")
    lines.append("")
    lines.append("المسح عبر REST للمحتوى المنشور (`post`, `page`, والخدمات والأنواع المخصصة). عدد الكلمات بعد إزالة HTML. عتبة المحتوى الضعيف: **أقل من 1000 كلمة**. التشابه: Jaccard على 5-grams بعد تطبيع أسماء المواقع، مع تجميع المقالات ذات هيكل H2 المطابق.")
    lines.append("")
    lines.append("## الخلاصة المهنية")
    lines.append("")
    lines.append(
        f"المشكلة الأساسية ليست «مقالات قصيرة» بقدر ما هي مصنع pSEO: {stats.get('boilerplate', 0)} عنصراً بنصوص نمطية، "
        f"{stats.get('near_dup_items', 0)} ضمن مجموعات متشابهة، و{stats.get('cannibal_items', 0)} في تآكل كلمات مفتاحية. "
        f"{stats.get('shared_image', 0)} عنصراً يشتركون في الصورة البارزة. متوسط الكلمات {stats.get('avg_post_words', 0)} "
        "مضخَّم بجداول وأسئلة مكررة وليس بقيمة فريدة."
    )
    lines.append("")
    lines.append("أولوية الإصلاح: دمج كل مجموعة أحياء إلى دليل إمارة واحد أو حذف/noindex الأضعف؛ بناء محتوى أصيل لخدمات الحديد والمظلات؛ إكمال صفحات الخدمات والمعرض.")
    lines.append("")
    lines.append("## ملخص تنفيذي")
    lines.append("")
    lines.append("| المؤشر | العدد |")
    lines.append("| --- | ---: |")
    for k, label in (
        ("total", "إجمالي العناصر"),
        ("posts", "مقالات"),
        ("pages", "صفحات"),
        ("cpts", "أنواع مخصصة"),
        ("thin", "أقل من 1000 كلمة"),
        ("very_thin", "أقل من 300 كلمة"),
        ("boilerplate", "قالب نمطي كثيف"),
        ("near_dup_items", "ضمن مجموعات متشابهة"),
        ("cannibal_items", "تآكل كلمات مفتاحية"),
        ("intent", "عدم توافق العنوان/المتن"),
        ("missing_h2", "H2 ناقص"),
        ("placeholder", "نصوص مؤقتة"),
        ("no_featured", "بدون صورة بارزة"),
        ("shared_image", "نفس الصورة البارزة"),
    ):
        lines.append(f"| {label} | {stats.get(k, 0)} |")
    lines.append("")
    lines.append(f"**متوسط الكلمات (مقالات):** {stats.get('avg_post_words', 0)}")
    lines.append("")
    if stats.get("top_skeletons"):
        lines.append("### أكثر هياكل H2 تكراراً (قوالب)")
        lines.append("")
        for skel, n in stats["top_skeletons"]:
            preview = skel[:120] + ("…" if len(skel) > 120 else "")
            lines.append(f"- **{n} مقالاً:** `{preview}`")
        lines.append("")
    if stats.get("cannibal_groups"):
        lines.append("### مجموعات تآكل الكلمات المفتاحية (أكبرها)")
        lines.append("")
        for key, n, sample in stats["cannibal_groups"][:12]:
            lines.append(f"- **{n} مقالات** لنفس النية تقريباً: `{key}` — مثال: {sample}")
        lines.append("")

    lines.append("## جدول المشكلات")
    lines.append("")
    lines.append("| العنوان | الرابط | الكلمات | الفئة | ملاحظات |")
    lines.append("| --- | --- | ---: | --- | --- |")
    flagged = [r for r in rows if r.get("issues")]
    flagged.sort(key=lambda r: (0 if "intent_mismatch" in r["issues"] else 1, r["word_count"]))
    for r in flagged:
        cats = "، ".join(issue_label(i) for i in r["issues"] if i != "no_content_h1")
        if not cats:
            continue
        notes = "؛ ".join(r["notes"][:3])
        title = md_escape(r["title"])[:80]
        url = r["url"]
        lines.append(f"| {title} | {url} | {r['word_count']} | {cats} | {md_escape(notes)[:220]} |")
    lines.append("")
    lines.append("الملف التفصيلي: [`seo-content-audit.csv`](seo-content-audit.csv).")
    lines.append("")
    lines.append("## ملاحظات منهجية")
    lines.append("")
    lines.append("- **H1:** معظم قوالب ووردبريس تطبع عنوان المقالة كـ H1 خارج `post_content`. غياب H1 داخل HTML المحتوى ليس خطأ فهرسة إذا كان القالب يعرض العنوان — لذلك لم تُحتسب وحدها مشكلة حرجة في الجدول.")
    lines.append("- **التشابه:** يقارن كل مقال بالمقالات ذات المعرّفات القريبة (دفعات النشر الجماعي). النسبة ≥ 0.78 تُعد تكراراً هيكلياً.")
    lines.append("- **النية:** تُستخرج من كلمات العنوان مقابل كثافة الموضوع في المتن، مع التحقق من ذكر الموقع الجغرافي المذكور في العنوان.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit published WordPress content for SEO quality")
    parser.add_argument("--out-dir", default=str(OUT_DIR))
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    url, user, password = config()
    print("fetching published content from", url, flush=True)
    rest_map = {
        "post": "posts",
        "page": "pages",
        "services": "services",
        "reviews": "reviews",
        "faqs": "faqs",
        "pricing": "pricing",
        "portfolio": "portfolio",
        "before_after": "before_after",
    }
    raw_items: list[dict[str, Any]] = []
    for typ, rest_base in rest_map.items():
        try:
            batch = fetch_type(url, user, password, rest_base)
        except Exception as exc:  # noqa: BLE001
            print("WARN", typ, exc, flush=True)
            continue
        raw_items.extend(batch)
        print(f"fetched {typ}: {len(batch)}", flush=True)

    print("analyzing", len(raw_items), "items", flush=True)
    rows = [analyze_item(it) for it in raw_items]

    # featured image concentration
    img_counts = Counter(r["featured_media"] for r in rows if r["featured_media"])
    common_img, common_n = img_counts.most_common(1)[0] if img_counts else (0, 0)
    if common_n >= 20:
        for r in rows:
            if r["featured_media"] == common_img:
                r["issues"].append("shared_featured_image")
                r["notes"].append(f"نفس الصورة البارزة مستخدمة على {common_n} عنصراً (ID {common_img})")

    # skeleton boilerplate
    skel_counts = Counter(r["h2_skeleton"] for r in rows if r["h2_skeleton"] and r["type"] == "post")
    heavy_skels = {s for s, n in skel_counts.items() if n >= 8 and len(s) > 20}
    for r in rows:
        if r["h2_skeleton"] in heavy_skels and "boilerplate" not in r["issues"]:
            r["issues"].append("boilerplate")
            r["notes"].append(f"هيكل H2 مطابق لـ {skel_counts[r['h2_skeleton']]} مقالاً آخر")

    # near-duplicates: same H2 skeleton (pSEO clones) + shingle clusters
    id_to_group: dict[int, str] = {}
    gid = 1
    skel_members: dict[str, list[int]] = defaultdict(list)
    for r in rows:
        if r["type"] == "post" and r["h2_skeleton"] and skel_counts.get(r["h2_skeleton"], 0) >= 3:
            skel_members[r["h2_skeleton"]].append(r["id"])
    for _skel, members in sorted(skel_members.items(), key=lambda kv: len(kv[1]), reverse=True):
        if len(members) < 3:
            continue
        label = f"DUP-{gid:03d} ({len(members)})"
        gid += 1
        for mid in members:
            id_to_group[mid] = label
    clusters = cluster_near_dupes(rows)
    for members in sorted(clusters.values(), key=len, reverse=True):
        already = [id_to_group[m] for m in members if m in id_to_group]
        if already:
            label = Counter(already).most_common(1)[0][0]
        else:
            label = f"DUP-{gid:03d} ({len(members)})"
            gid += 1
        for mid in members:
            id_to_group.setdefault(mid, label)
    for r in rows:
        if r["id"] in id_to_group:
            r["duplicate_group"] = id_to_group[r["id"]]
            if "near_duplicate" not in r["issues"]:
                r["issues"].append("near_duplicate")
                r["notes"].append("متشابه جداً مع مقالات أخرى في " + id_to_group[r["id"]])
        else:
            r["duplicate_group"] = ""

    # cannibalization
    can_groups = defaultdict(list)
    for r in rows:
        if r["type"] == "post" and r["cannibal_key"]:
            can_groups[r["cannibal_key"]].append(r)
    can_id = 1
    can_summary = []
    for key, members in sorted(can_groups.items(), key=lambda kv: len(kv[1]), reverse=True):
        if len(members) < CANNIBAL_MIN_GROUP:
            continue
        label = f"CAN-{can_id:03d} ({len(members)})"
        can_id += 1
        sample = members[0]["title"]
        can_summary.append((key, len(members), sample))
        for r in members:
            r["cannibal_group"] = label
            if "cannibalization" not in r["issues"]:
                r["issues"].append("cannibalization")
                r["notes"].append(f"{len(members)} مقالات تتنافس على نية شبه مطابقة")
        else:
            pass
    for r in rows:
        r.setdefault("cannibal_group", "")

    posts = [r for r in rows if r["type"] == "post"]
    avg = int(sum(r["word_count"] for r in posts) / len(posts)) if posts else 0

    def count_issue(code: str) -> int:
        return sum(1 for r in rows if code in r["issues"])

    stats = {
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "total": len(rows),
        "posts": len(posts),
        "pages": sum(1 for r in rows if r["type"] == "page"),
        "cpts": sum(1 for r in rows if r["type"] not in ("post", "page")),
        "thin": count_issue("thin_content"),
        "very_thin": count_issue("very_thin"),
        "boilerplate": count_issue("boilerplate"),
        "near_dup_items": count_issue("near_duplicate"),
        "cannibal_items": count_issue("cannibalization"),
        "intent": count_issue("intent_mismatch"),
        "missing_h2": count_issue("missing_h2"),
        "placeholder": count_issue("placeholder"),
        "no_featured": count_issue("missing_featured_image"),
        "shared_image": count_issue("shared_featured_image"),
        "avg_post_words": avg,
        "top_skeletons": skel_counts.most_common(8),
        "cannibal_groups": can_summary,
    }

    # drop heavy fields before csv
    for r in rows:
        r.pop("shingles", None)
        # unique issues
        seen = set()
        uniq = []
        for i in r["issues"]:
            if i not in seen:
                seen.add(i)
                uniq.append(i)
        r["issues"] = uniq

    csv_path = out_dir / "seo-content-audit.csv"
    md_path = out_dir / "SEO_CONTENT_AUDIT.md"
    write_csv(csv_path, sorted(rows, key=lambda r: (r["type"], -r["word_count"])))
    write_markdown(md_path, rows, stats)
    summary_path = out_dir / "seo-content-audit-summary.json"
    json_stats = {k: v for k, v in stats.items() if k not in ("top_skeletons", "cannibal_groups")}
    json_stats["top_skeletons"] = [{"skeleton": s, "count": n} for s, n in stats["top_skeletons"][:8]]
    json_stats["cannibal_groups"] = [
        {"key": k, "count": n, "sample": sample} for k, n, sample in stats["cannibal_groups"][:20]
    ]
    summary_path.write_text(json.dumps(json_stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", csv_path)
    print("wrote", md_path)
    print("wrote", summary_path)
    print(json.dumps(json_stats, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
