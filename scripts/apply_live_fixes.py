#!/usr/bin/env python3
"""Apply remaining live content/SEO fixes on max-art-ae.com.

Uses WordPress REST + WPVibe CLI. Credentials come from /workspace/.env.
Never prints the application password.
"""

from __future__ import annotations

import base64
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from wp_connect import config  # noqa: E402

UA = "max-art-ae-cursor-connect/1.0"
PHONE = "+971544437175"
PHONE_DISPLAY = "+971 54 443 7175"
WA = "971544437175"
WA_URL = f"https://wa.me/{WA}"
LOGO_ID = 3362
LOGO_URL = "https://max-art-ae.com/wp-content/uploads/2026/07/1783747619594.webp"


def _auth_header(user: str, password: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


def request(
    url: str,
    user: str,
    password: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 90,
) -> Any:
    body = None
    headers = {
        "Authorization": _auth_header(user, password),
        "Accept": "application/json",
        "User-Agent": UA,
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    last: Exception | None = None
    for attempt in range(6):
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                if not raw:
                    return None
                try:
                    return json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {method} {url}\n{detail[:2000]}") from exc
        except Exception as exc:  # noqa: BLE001 — retry SSL/reset
            last = exc
            time.sleep(1.4 * (attempt + 1))
    raise RuntimeError(f"request failed after retries: {last}")


def rest(base: str, user: str, password: str, path: str, method: str = "GET", payload: dict | None = None) -> Any:
    if not path.startswith("/"):
        path = "/" + path
    target = f"{base}{path}" if path.startswith("/wp-json") else f"{base}/wp-json{path}"
    return request(target, user, password, method=method, payload=payload)


def cli(base: str, user: str, password: str, command: str, confirm: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {"command": command}
    if confirm:
        payload["confirm_write"] = True
    data = request(f"{base}/wp-json/wpvibe/v1/cli/run", user, password, method="POST", payload=payload)
    if not isinstance(data, dict):
        return {"stdout": str(data), "stderr": "", "exit_code": 1}
    return data


def log_cli(label: str, data: dict[str, Any]) -> None:
    code = data.get("exit_code")
    out = (data.get("stdout") or "").strip()
    err = (data.get("stderr") or "").strip()
    print(f"[{label}] exit={code}")
    if out:
        print(out[:1500])
    if err:
        print("stderr:", err[:800])


ROOF_HTML = f"""<p>شركة ماكس آرت تنفّذ عزل أسطح احترافي في الإمارات منذ 2008: عزل مائي وحراري للأسطح الخرسانية والمعدنية، مع معاينة مجانية وضمان مكتوب على التنفيذ.</p>
<h2>ماذا يشمل العمل؟</h2>
<ul>
<li>كشف التشققات ونقاط ضعف الميلان قبل التنفيذ</li>
<li>عزل مائي ضد الأمطار والرطوبة وتسرب الخزانات</li>
<li>عزل حراري يقلّل استهلاك التكييف صيفاً</li>
<li>معالجة المصارف وإعادة طبقة الحماية النهائية</li>
</ul>
<h2>التغطية</h2>
<p>دبي، الشارقة، عجمان، أبوظبي وبقية الإمارات حسب جدولة المعاينة.</p>
<p><a href="{WA_URL}">اطلب معاينة عبر واتساب</a> أو اتصل <a href="tel:{PHONE}">{PHONE_DISPLAY}</a>.</p>
"""

LEAK_HTML = f"""<p>كشف تسربات المياه بأجهزة حديثة دون تكسير عشوائي. فريق ماكس آرت يحدّد مصدر التسرب في الأرضيات والجدران والأسطح والخزانات، ثم يقدّم تقرير معاينة وخطة إصلاح.</p>
<h2>متى تحتاج كشف تسرب؟</h2>
<ul>
<li>ارتفاع فاتورة المياه دون سبب واضح</li>
<li>رطوبة أو تقشير دهان أو رائحة عفن</li>
<li>هبوط بلاط أو بقع على السقف</li>
<li>تسرب حول الخزان أو مواسير التغذية</li>
</ul>
<h2>بعد الكشف</h2>
<p>نحدد سبب التسرب ونفّذ العزل أو إصلاح السباكة حسب الحالة، مع ضمان مكتوب.</p>
<p><a href="{WA_URL}">تواصل واتساب الآن</a> — <a href="tel:{PHONE}">{PHONE_DISPLAY}</a>.</p>
"""

PRIVACY_HTML = f"""<p>تحترم شركة ماكس آرت خصوصيتكم. توضح هذه السياسة كيف نتعامل مع البيانات عند زيارة <a href="https://max-art-ae.com">max-art-ae.com</a> أو التواصل معنا لطلب صيانة أو معاينة في الإمارات.</p>
<h2>البيانات التي قد نجمعها</h2>
<ul>
<li>الاسم ورقم الهاتف ورسالة الطلب عند التواصل عبر واتساب أو الهاتف أو نموذج الموقع</li>
<li>عنوان أو منطقة التنفيذ لتحديد موعد المعاينة</li>
<li>بيانات تقنية معتادة مثل عنوان IP ونوع المتصفح عبر ملفات تعريف الارتباط وإحصاءات الاستضافة</li>
</ul>
<h2>الاستخدام</h2>
<p>نستخدم البيانات للرد على طلباتكم، جدولة المعاينة، تحسين الموقع، والالتزام بالمتطلبات النظامية في دولة الإمارات. لا نبيع بياناتكم لأطراف تسويقية.</p>
<h2>واتساب والهاتف</h2>
<p>المراسلات عبر واتساب أو الاتصال على {PHONE_DISPLAY} تخضع أيضاً لسياسات تلك المنصات. احتفظوا بنسخة من أي اتفاق مكتوب يصلكم من فريقنا.</p>
<h2>ملفات تعريف الارتباط</h2>
<p>قد يستخدم الموقع كوكيز للتشغيل الأساسي وقياس الأداء والتخزين المؤقت. يمكنكم ضبط المتصفح لرفض الكوكيز غير الضرورية.</p>
<h2>التواصل</h2>
<p>لطلب تصحيح أو حذف بيانات التواصل: واتساب <a href="{WA_URL}">{PHONE_DISPLAY}</a> أو البريد support@max-art-ae.com.</p>
"""

ABOUT_HTML = f"""<p>ماكس آرت شركة صيانة عامة وأعمال حدادة في الإمارات منذ 2008. ورشة تصنيع خاصة، ومعاينة مجانية، وضمان مكتوب على التنفيذ.</p>
<h2>ماذا نقدّم؟</h2>
<ul>
<li>أعمال حدادة وتصنيع معدني</li>
<li>تصميم وتركيب مظلات وسواتر وبرجولات</li>
<li>صيانة وترميم مباني وتشطيبات وديكورات</li>
<li>سباكة وكهرباء وعزل أسطح وكشف تسربات</li>
</ul>
<h2>التغطية</h2>
<p>نخدم دبي والشارقة وعجمان وأبوظبي وبقية الإمارات حسب جدولة الفريق.</p>
<p><a href="/contact-us/">صفحة التواصل</a> — واتساب <a href="{WA_URL}">{PHONE_DISPLAY}</a>.</p>
"""

CONTACT_HTML = f"""<p>تواصلوا مع شركة ماكس آرت لطلب معاينة أو عرض سعر. الرد عبر واتساب أو الاتصال مباشرة.</p>
<h2>بيانات التواصل</h2>
<ul>
<li>الهاتف: <a href="tel:{PHONE}">{PHONE_DISPLAY}</a></li>
<li>واتساب: <a href="{WA_URL}">{PHONE_DISPLAY}</a></li>
<li>البريد: <a href="mailto:support@max-art-ae.com">support@max-art-ae.com</a></li>
<li>العنوان: دبي، الإمارات العربية المتحدة — المعاينة في موقعكم</li>
</ul>
<h2>ساعات العمل</h2>
<p>السبت–الخميس 08:00–22:00، الجمعة من 16:00–22:00 (حسب مواعيد المعاينة).</p>
<p><a href="{WA_URL}">ابدأ المحادثة على واتساب</a></p>
"""

BLOG_HTML = "<p>مقالات شركة ماكس آرت عن الصيانة العامة، كشف التسربات، العزل، وأعمال الحديد والمظلات في الإمارات.</p>"

FAQ_HTML = f"""<h2>هل المعاينة مجانية؟</h2>
<p>نعم، المعاينة الميدانية مجانية داخل نطاق التغطية المعتاد في الإمارات، ويُؤكد الموعد عبر واتساب.</p>
<h2>هل يتوفر ضمان؟</h2>
<p>نكتب الضمان على الأعمال المتفق عليها بعد المعاينة، ومدة الضمان تختلف حسب نوع العزل أو الإصلاح.</p>
<h2>كم يستغرق التنفيذ؟</h2>
<p>يُحدد بعد المعاينة حسب مساحة السطح أو حجم التسرب وتوفر المواد.</p>
<p>للسؤال مباشرة: <a href="{WA_URL}">{PHONE_DISPLAY}</a>.</p>
"""

REVIEW_HTML = f"""<p>تقييم عميل لماكس آرت بعد تنفيذ أعمال صيانة في الإمارات. نوثّق الأعمال بعد المعاينة ونلتزم بالموعد والضمان المكتوب.</p>
<p>اطلب زيارة مماثلة عبر <a href="{WA_URL}">واتساب</a>.</p>
"""

PRICING_HTML = f"""<p>أسعار ماكس آرت تُحدد بعد المعاينة حسب المساحة ونوع العزل أو الإصلاح وطبيعة الموقع. لا توجد قائمة ثابتة تغني عن كشف ميداني.</p>
<p>اطلب عرض سعر: <a href="{WA_URL}">{PHONE_DISPLAY}</a>.</p>
"""

PORTFOLIO_HTML = f"""<p>أعمال سابقة لشركة ماكس آرت في الإمارات: حدادة، مظلات وسواتر، عزل أسطح، وكشف تسربات. نعرض نماذج العمل بعد الاتفاق مع العميل.</p>
<p>لطلب تنفيذ مشابه: <a href="{WA_URL}">{PHONE_DISPLAY}</a>.</p>
"""

BEFORE_AFTER_HTML = f"""<p>قبل وبعد أعمال العزل وكشف التسربات والصيانة. نوثّق الحالة عند المعاينة ثم بعد التنفيذ مع ضمان مكتوب.</p>
<p><a href="{WA_URL}">أرسل صوراً عبر واتساب لتقييم مبدئي</a>.</p>
"""


def b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def main() -> int:
    url, user, password = config()
    print("site", url)

    # --- pages ---
    log_cli("mpg draft", cli(url, user, password, "post update 3625 --post_status=draft", confirm=True))
    log_cli(
        "mpg robots meta",
        cli(
            url,
            user,
            password,
            'post meta update 3625 rank_math_robots ["noindex","nofollow"] --format=json --force',
            confirm=True,
        ),
    )

    log_cli(
        "privacy",
        cli(
            url,
            user,
            password,
            f"post update 3 --post_title='سياسة الخصوصية' --post_content_base64={b64(PRIVACY_HTML)} --post_status=publish",
            confirm=True,
        ),
    )
    log_cli(
        "blog title",
        cli(
            url,
            user,
            password,
            f"post update 153 --post_title='المدونة' --post_content_base64={b64(BLOG_HTML)} --post_status=publish",
            confirm=True,
        ),
    )

    # create about / contact if missing
    existing = rest(url, user, password, "/wp/v2/pages?per_page=50&slug=about-us,contact-us,about,contact")
    slugs = {p.get("slug"): p.get("id") for p in existing or []}
    print("existing slugs", slugs)

    if "about-us" not in slugs and "about" not in slugs:
        created = rest(
            url,
            user,
            password,
            "/wp/v2/pages",
            method="POST",
            payload={
                "title": "من نحن",
                "slug": "about-us",
                "status": "publish",
                "content": ABOUT_HTML,
                "featured_media": LOGO_ID,
            },
        )
        print("created about-us", created.get("id"), created.get("link"))
        slugs["about-us"] = created.get("id")
    else:
        aid = slugs.get("about-us") or slugs.get("about")
        rest(
            url,
            user,
            password,
            f"/wp/v2/pages/{aid}",
            method="POST",
            payload={"title": "من نحن", "content": ABOUT_HTML, "status": "publish", "featured_media": LOGO_ID},
        )
        print("updated about", aid)

    if "contact-us" not in slugs and "contact" not in slugs:
        created = rest(
            url,
            user,
            password,
            "/wp/v2/pages",
            method="POST",
            payload={
                "title": "تواصل معنا",
                "slug": "contact-us",
                "status": "publish",
                "content": CONTACT_HTML,
                "featured_media": LOGO_ID,
            },
        )
        print("created contact-us", created.get("id"), created.get("link"))
        slugs["contact-us"] = created.get("id")
    else:
        cid = slugs.get("contact-us") or slugs.get("contact")
        rest(
            url,
            user,
            password,
            f"/wp/v2/pages/{cid}",
            method="POST",
            payload={"title": "تواصل معنا", "content": CONTACT_HTML, "status": "publish", "featured_media": LOGO_ID},
        )
        print("updated contact", cid)

    # --- services + other CPTs ---
    log_cli(
        "roof",
        cli(
            url,
            user,
            password,
            f"post update 3518 --post_content_base64={b64(ROOF_HTML)} --post_excerpt='عزل أسطح مائي وحراري في الإمارات مع معاينة مجانية من ماكس آرت.'",
            confirm=True,
        ),
    )
    log_cli(
        "leak",
        cli(
            url,
            user,
            password,
            f"post update 3317 --post_content_base64={b64(LEAK_HTML)} --post_excerpt='كشف تسربات المياه في الإمارات دون تكسير عشوائي، مع تقرير معاينة من ماكس آرت.'",
            confirm=True,
        ),
    )
    for pid, html, excerpt in (
        (3618, FAQ_HTML, "أسئلة شائعة عن المعاينة والضمان ومدة التنفيذ في ماكس آرت."),
        (3601, REVIEW_HTML, "تقييم عميل لأعمال صيانة ماكس آرت في الإمارات."),
        (3623, PRICING_HTML, "تُحدد الأسعار بعد المعاينة حسب المساحة ونوع العمل."),
        (3621, PORTFOLIO_HTML, "نماذج أعمال ماكس آرت في الحدادة والمظلات والعزل."),
        (3620, BEFORE_AFTER_HTML, "توثيق قبل وبعد أعمال العزل وكشف التسربات."),
    ):
        log_cli(
            f"cpt {pid}",
            cli(
                url,
                user,
                password,
                f"post update {pid} --post_content_base64={b64(html)} --post_excerpt='{excerpt}'",
                confirm=True,
            ),
        )

    # --- search replace (posts table only to avoid serialised option breakage) ---
    replacements = [
        ("97431110184", "971544437175"),
        ("97431553076", "971544437175"),
        ("+97431110184", "+971544437175"),
        ("+97431553076", "+971544437175"),
        ("tel:+97431110184", "tel:+971544437175"),
        ("tel:+97431553076", "tel:+971544437175"),
        ("خالد المطيري", "فريق ماكس آرت"),
        ("ركن التطور", "ماكس آرت"),
        ("شهادة ISO 9001", "ضمان مكتوب"),
    ]
    for old, new in replacements:
        log_cli(
            f"sr {old}",
            cli(
                url,
                user,
                password,
                f'search-replace "{old}" "{new}" wpt0_posts wpt0_postmeta --skip-columns=guid',
                confirm=True,
            ),
        )

    # --- Rank Math / identity ---
    patches = [
        'option patch update rank-math-options-titles knowledgegraph_name "شركة ماكس آرت"',
        'option patch update rank-math-options-titles website_name "شركة ماكس آرت"',
        'option patch update rank-math-options-titles website_alternate_name "ماكس آرت"',
        'option patch update rank-math-options-titles homepage_title "شركة ماكس آرت للصيانة في الإمارات"',
        'option patch update rank-math-options-titles homepage_description "صيانة عامة وحدادة ومظلات وعزل في الإمارات منذ 2008. معاينة مجانية على واتساب."',
        "option patch update rank-math-options-titles disable_author_archives on",
        f'option patch update rank-math-options-titles knowledgegraph_logo "{LOGO_URL}"',
        "option patch update rank-math-options-titles knowledgegraph_logo_id 3362",
        "option patch update rank-math-options-sitemap pt_page_sitemap on",
        "option patch update rank-math-options-sitemap pt_services_sitemap on",
        "option patch update rank-math-options-sitemap authors_sitemap false --format=json",
        'option update kayan_booking_notify_email "support@max-art-ae.com"',
        'option update youtube ""',
        'option update telegram ""',
        'option update footer__company__adress_url "https://maps.google.com/?q=Dubai,United+Arab+Emirates"',
        "option add kayan_i18n_disable 1",
    ]
    hours = json.dumps(
        [
            {"day": "Saturday", "time": "08:00-22:00"},
            {"day": "Sunday", "time": "08:00-22:00"},
            {"day": "Monday", "time": "08:00-22:00"},
            {"day": "Tuesday", "time": "08:00-22:00"},
            {"day": "Wednesday", "time": "08:00-22:00"},
            {"day": "Thursday", "time": "08:00-22:00"},
            {"day": "Friday", "time": "16:00-22:00"},
        ],
        ensure_ascii=False,
    )
    patches.append(
        "option patch update rank-math-options-titles opening_hours '" + hours.replace("'", "") + "' --format=json"
    )
    for cmd in patches:
        log_cli(cmd.split()[2] if cmd.startswith("option patch") else cmd[:40], cli(url, user, password, cmd, confirm=True))

    # city slugs
    log_cli("dubai slug", cli(url, user, password, "term update cities 65 --by=id --slug=dubai", confirm=True))
    log_cli("fujairah slug", cli(url, user, password, "term update cities 70 --by=id --slug=fujairah", confirm=True))

    # nav
    nav = [
        (3287, "https://max-art-ae.com/services/"),
        (3288, "https://max-art-ae.com/#areas"),
        (3289, "https://max-art-ae.com/portfolio/"),
        (3290, "https://max-art-ae.com/blog/"),
        (3291, "https://max-art-ae.com/about-us/"),
        (3292, "https://max-art-ae.com/faqs/"),
    ]
    for db_id, link in nav:
        log_cli(f"menu {db_id}", cli(url, user, password, f"menu item update {db_id} --link={link}", confirm=True))
    log_cli(
        "menu contact",
        cli(
            url,
            user,
            password,
            'menu item add-custom "القائمة الرئيسية" "تواصل معنا" https://max-art-ae.com/contact-us/ --position=7 --porcelain',
            confirm=True,
        ),
    )

    # footer services menu
    created_menu = cli(url, user, password, 'menu create "خدمات التذييل" --porcelain', confirm=True)
    log_cli("menu create footer", created_menu)
    menu_id = (created_menu.get("stdout") or "").strip()
    if menu_id.isdigit():
        for title, link in (
            ("كشف تسربات المياه", "https://max-art-ae.com/services/leak-detection/"),
            ("عزل أسطح", "https://max-art-ae.com/services/roof-insulation/"),
            ("تواصل معنا", "https://max-art-ae.com/contact-us/"),
        ):
            log_cli(
                f"footer item {title}",
                cli(
                    url,
                    user,
                    password,
                    f'menu item add-custom {menu_id} "{title}" {link} --porcelain',
                    confirm=True,
                ),
            )
        log_cli(
            "assign footer menu",
            cli(url, user, password, f"option update footer__second_menu {menu_id}", confirm=True),
        )

    log_cli("cache purge", cli(url, user, password, "cache purge all", confirm=True))
    print("content phase done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
