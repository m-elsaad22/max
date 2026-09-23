#!/usr/bin/env python3
"""Rewrite live homepage copy to lead with leak detection and roof insulation.

Updates HomeIntro, Rank Math homepage SEO, blogdescription, and homepage
widget copy on max-art-ae.com.

WPVibe cannot `post meta update` the theme's `widgets__posts` type, so the
script clones each homepage widget onto a normal draft post (maxart-hp-*)
and retargets `widgets_home__meta` at those IDs.
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import cli, config, log_cli  # noqa: E402

CITY_SERVICES = (
    "كشف تسربات المياه\n"
    "عزل الأسطح\n"
    "معالجة الرطوبة\n"
    "ارتفاع فاتورة المياه\n"
    "صيانة عامة وترميم\n"
    "حدادة ومظلات\n"
    "تشطيبات وأرضيات"
)

FINDER_SERVICES = "\n".join(
    [
        "كشف تسربات المياه",
        "عزل أسطح",
        "معالجة الرطوبة",
        "حل ارتفاع فاتورة المياه",
        "صيانة عامة",
        "صيانة مباني",
        "ترميم منازل قديمة",
        "حدادة وتشكيل معادن",
        "تصميم وبناء مظلات",
        "تركيب مظلات وسواتر",
        "تركيب برجولات",
        "حداد أبواب ونوافذ",
        "صيانة كهرباء",
        "سباك منازل",
        "صيانة سباكة",
        "تسليك مجاري",
        "تركيب وصيانة تكييف",
        "تركيب حجر طبيعي وصناعي",
        "تركيب رخام وجرانيت",
        "تركيب سيراميك وبورسلين",
        "تركيب باركيه",
        "تصميم وتنفيذ ديكورات",
        "تركيب جبس بورد",
        "صبغ",
        "تركيب مطابخ",
        "تركيب أبواب وشبابيك",
        "تنسيق حدائق",
        "إنشاء وصيانة مسابح",
    ]
)


def option_json(url: str, user: str, password: str, name: str, value) -> None:
    encoded = json.dumps(json.dumps(value, ensure_ascii=False))
    log_cli(
        f"option {name}",
        cli(
            url,
            user,
            password,
            f"option update {name} {encoded} --format=json",
            confirm=True,
        ),
    )


def get_option_json(url: str, user: str, password: str, name: str):
    raw = cli(url, user, password, f"option get {name} --format=json").get("stdout") or "null"
    return json.loads(raw)


def get_meta_json(url: str, user: str, password: str, pid: int, key: str):
    raw = cli(url, user, password, f"post meta get {pid} {key} --format=json").get("stdout") or "null"
    return json.loads(raw)


def patch_home_intro(intro: dict) -> dict:
    data = deepcopy(intro)
    slider = data.setdefault("slider_intro_v1", {})
    slider["title"] = "ماكس آرت — {%كشف التسربات وعزل الأسطح%} في الإمارات منذ 2008"
    slider["sub_text"] = (
        "نكشف تسربات المياه دون تكسير عشوائي، نعزل الأسطح مائياً وحرارياً، نعالج الرطوبة، "
        "ونوقف هدر المياه الذي يرفع فاتورتك. وبعد ذلك نغطي الصيانة العامة والحدادة والمظلات "
        "والتشطيبات — فريق مقيم في دبي منذ 2008 بضمان مكتوب."
    )
    slider["dash_title"] = "لوحة خدمات ماكس آرت"
    slider["warranty_title"] = "ضمان مكتوب على كل عمل"
    slider["warranty_sub"] = "على كشف التسربات والعزل والصيانة"
    chips = slider.get("proof_chips") or {}
    chip_titles = [
        "18 سنة خبرة منذ 2008",
        "نغطي الإمارات السبع",
        "ضمان مكتوب على التنفيذ",
        "كشف دون تكسير عشوائي",
        "معاينة وزيارة موقع",
        "استجابة سريعة",
    ]
    for chip, title in zip(chips.values(), chip_titles):
        if isinstance(chip, dict):
            chip["title"] = title
    services = [
        ("fas fa-magnifying-glass", "كشف تسربات المياه"),
        ("fas fa-layer-group", "عزل الأسطح"),
        ("fas fa-droplet", "معالجة الرطوبة"),
        ("fas fa-file-invoice", "ارتفاع فاتورة المياه"),
        ("fas fa-screwdriver-wrench", "صيانة عامة"),
        ("fas fa-hammer", "حدادة ومظلات"),
    ]
    dash = slider.get("dash_services") or {}
    for item, (icon, title) in zip(dash.values(), services):
        if isinstance(item, dict):
            item["icon"] = f'<i class="{icon}"></i>'
            item["title"] = title
    return data


def patch_finder(meta: dict) -> dict:
    data = deepcopy(meta)
    data["before_title"] = "ابدأ الآن"
    data["title"] = "ما الخدمة التي {%تحتاجها؟%}"
    data["content"] = (
        "ابدأ بكشف التسربات أو عزل الأسطح أو معالجة الرطوبة أو ارتفاع فاتورة المياه، "
        "ثم اختر المنطقة — ونتواصل لتحديد معاينة مجانية."
    )
    data["manual_services"] = FINDER_SERVICES
    data["result_sub_template"] = (
        "فريق ماكس آرت في {city}: كشف تسربات وعزل أسطح وصيانة — معاينة مجانية قبل البدء."
    )
    data["button_text"] = "اطلب معاينة مجانية"
    return data


def patch_services(meta: dict) -> dict:
    data = deepcopy(meta)
    data["before_title"] = "خدماتنا"
    data["title"] = "التركيز على {%كشف التسربات وعزل الأسطح%}"
    data["content"] = (
        "الأولوية لكشف تسربات المياه وعزل الأسطح ومعالجة الرطوبة ووقف ارتفاع فاتورة المياه. "
        "وبعدها صيانة عامة وحدادة ومظلات وتشطيبات تحت مسؤولية واحدة."
    )
    data["manual_cards"] = [
        {
            "icon": '<i class="fas fa-magnifying-glass"></i>',
            "title": "كشف تسربات المياه",
            "desc": "تحديد مصدر التسرب بأجهزة حديثة دون تكسير عشوائي، مع تقرير قبل الإصلاح.",
            "features": "كشف تسربات المياه\nكشف دون تكسير عشوائي\nتسربات الأرضيات والجدران\nتسرب الخزانات والمواسير",
            "url": "",
        },
        {
            "icon": '<i class="fas fa-layer-group"></i>',
            "title": "عزل الأسطح",
            "desc": "عزل مائي وحراري للأسطح الخرسانية والمعدنية يحمي المبنى من الأمطار والحرارة.",
            "features": "عزل مائي ضد الأمطار\nعزل حراري للأسطح\nمعالجة الميلان والمصارف\nطبقة حماية بضمان مكتوب",
            "url": "",
        },
        {
            "icon": '<i class="fas fa-droplet"></i>',
            "title": "معالجة الرطوبة وفاتورة المياه",
            "desc": "نعالج الرطوبة من مصدرها ونوقف الهدر الذي يرفع فاتورة المياه دون سبب واضح.",
            "features": "معالجة رطوبة الجدران والأسقف\nحل ارتفاع فاتورة المياه\nإزالة العفن بعد التجفيف\nإصلاح المصدر لا الطلاء فوقه",
            "url": "",
        },
        {
            "icon": '<i class="fas fa-screwdriver-wrench"></i>',
            "title": "الصيانة والترميم",
            "desc": "صيانة عامة للمباني بعد وقف التسرب، من مهمة صغيرة إلى عقد صيانة.",
            "features": "صيانة عامة\nصيانة مباني\nترميم منازل قديمة\nبناء ملاحق\nصيانة كهرباء وسباكة",
            "url": "",
        },
        {
            "icon": '<i class="fas fa-hammer"></i>',
            "title": "أعمال الحدادة",
            "desc": "تشكيل وتصنيع الحديد بالمقاس في ورشتنا الخاصة.",
            "features": "حداد أبواب ونوافذ\nدرابزين وهياكل حديد\nأعمال حديد حسب الطلب\nصيانة وإصلاح المشغولات",
            "url": "",
        },
        {
            "icon": '<i class="fas fa-warehouse"></i>',
            "title": "مظلات وسواتر وبرجولات",
            "desc": "تصميم وتصنيع وتركيب بخامات تتحمل مناخ الإمارات.",
            "features": "تصميم وبناء مظلات\nمظلات سيارات ومداخل\nسواتر خصوصية\nبرجولات حديد وخشب وألمنيوم",
            "url": "",
        },
        {
            "icon": '<i class="fas fa-gem"></i>',
            "title": "الأرضيات والأحجار",
            "desc": "قص وتركيب وتلميع بدقة وأقل فواصل — بعد معالجة التسرب إن وُجد.",
            "features": "رخام وجرانيت\nحجر طبيعي وصناعي\nسيراميك وبورسلين\nباركيه وانترلوك",
            "url": "",
        },
        {
            "icon": '<i class="fas fa-couch"></i>',
            "title": "الديكور والتشطيبات",
            "desc": "تصميم داخلي وتنفيذ كامل بعد معالجة الرطوبة حتى لا يعود التقشير.",
            "features": "تصميم وتنفيذ ديكورات\nجبس بورد\nصبغ داخلي وخارجي\nعازل صوت",
            "url": "",
        },
        {
            "icon": '<i class="fas fa-snowflake"></i>',
            "title": "التكييف والمساحات الخارجية",
            "desc": "تركيب وصيانة تكييف وكشف تسربه، مع حدائق ومطابخ حسب الحاجة.",
            "features": "تركيب وصيانة تكييف\nكشف تسرب التكييف\nتركيب مطابخ وألوميتال\nتنسيق حدائق ومسابح",
            "url": "",
        },
    ]
    return data


def patch_benefits(meta: dict) -> dict:
    data = deepcopy(meta)
    data["before_title"] = "لماذا نحن"
    data["title"] = "لماذا يختار العملاء {%ماكس آرت؟%}"
    data["content"] = (
        "نبدأ من مصدر المشكلة: كشف التسرب وعزل السطح ومعالجة الرطوبة، "
        "ثم نكمل الصيانة والحدادة تحت مسؤولية واحدة."
    )
    data["timeline_title"] = "رحلتك معنا بسيطة وواضحة"
    data["timeline_sub"] = "من أول اتصال إلى التسليم بضمان مكتوب على العزل والإصلاح."
    data["timeline_steps"] = [
        {
            "step_title": "تواصل ومعاينة مجانية",
            "step_desc": "نزور الموقع ونحدد مصدر التسرب أو نقيّم السطح والرطوبة بدون رسوم.",
        },
        {
            "step_title": "تقرير وعرض سعر مكتوب",
            "step_desc": "تقرير بالمصدر والخامة والمدة والتكلفة — بلا بنود مخفية.",
        },
        {
            "step_title": "الإصلاح والعزل في الموقع",
            "step_desc": "نعالج المصدر ثم نعزل أو نرمّم — وفريقنا هو من ينفّذ.",
        },
        {
            "step_title": "التسليم والضمان",
            "step_desc": "تسليم بعد معاينتك، مع ضمان مكتوب على كشف التسربات والعزل.",
        },
    ]
    data["feature_cards"] = [
        {
            "icon": '<i class="fas fa-magnifying-glass"></i>',
            "title": "كشف بأجهزة حديثة",
            "desc": "تحديد التسرب دون تكسير عشوائي في الأرضيات والجدران والأسطح.",
        },
        {
            "icon": '<i class="fas fa-layer-group"></i>',
            "title": "عزل مائي وحراري",
            "desc": "طبقات عزل تناسب سطح فيلتك ومناخ الإمارات، بضمان مكتوب.",
        },
        {
            "icon": '<i class="fas fa-file-invoice"></i>',
            "title": "حل ارتفاع الفاتورة",
            "desc": "نوقف هدر المياه من المصدر بدل التخمين أو تغيير العداد فقط.",
        },
        {
            "icon": '<i class="fas fa-award"></i>',
            "title": "خبرة منذ 2008",
            "desc": "18 عاماً في الرطوبة والملوحة وحرارة الأسطح في الإمارات.",
        },
        {
            "icon": '<i class="fas fa-screwdriver-wrench"></i>',
            "title": "صيانة وحدادة لاحقاً",
            "desc": "بعد وقف التسرب: صيانة عامة وحدادة ومظلات وتشطيبات من نفس الشركة.",
        },
        {
            "icon": '<i class="fas fa-map-location-dot"></i>',
            "title": "تغطية 10 مناطق",
            "desc": "من أبوظبي والعين إلى خورفكان ودبا.",
        },
    ]
    return data


def patch_stats(meta: dict) -> dict:
    data = deepcopy(meta)
    data["content"] = "سجل عمل منذ 2008 في كشف التسربات وعزل الأسطح والصيانة."
    return data


def patch_compare(meta: dict) -> dict:
    data = deepcopy(meta)
    data["content"] = "مقارنة صريحة بين طريقتنا في كشف التسربات والعزل وما هو شائع في السوق."
    rows = list(data.get("compare_rows") or [])
    rewrites = [
        ("ورشة تصنيع مملوكة للشركة", "كشف تسرب دون تكسير عشوائي"),
        ("معاينة الموقع قبل التسعير", "معاينة التسرب والعزل أولاً"),
        ("عرض سعر مكتوب ومفصّل", "عرض سعر مكتوب للعزل والإصلاح"),
        ("فريق تركيب موظّف لدى الشركة", "فريق كشف وعزل موظّف لدينا"),
        ("عدد الخدمات", "تركيز التسربات والعزل"),
        ("تخصص واحد", "خدمات عامة فقط"),
    ]
    by_old = {old: new for old, new in rewrites}
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = row.get("label")
        if label in by_old:
            row["label"] = by_old[label]
        if row.get("others_text") in by_old:
            row["others_text"] = by_old[row["others_text"]]
    data["compare_rows"] = rows
    return data


def patch_cities(meta: dict) -> dict:
    data = deepcopy(meta)
    data["content"] = (
        "مقرنا دبي، وفريق كشف التسربات والعزل والصيانة يصل إليك في أي منطقة أدناه."
    )
    for city in data.get("manual_cities") or []:
        if isinstance(city, dict):
            city["services"] = CITY_SERVICES
    return data


def patch_hub(meta: dict) -> dict:
    data = deepcopy(meta)
    data["before_title"] = "مركز المعرفة"
    data["title"] = "دليل {%التسربات والعزل والصيانة%}"
    data["content"] = "محتوى يساعدك تفهم مصدر التسرب ونوع العزل المناسب قبل ما تبدأ."
    data["hub_columns"] = [
        {
            "icon": '<i class="fas fa-magnifying-glass"></i>',
            "hub_title": "كشف التسربات",
            "guide_title": "دليل كشف تسربات المياه",
            "guide_url": "",
            "links": "علامات التسرب المخفي |\nكشف دون تكسير |\nتسرب الخزان والمواسير |",
        },
        {
            "icon": '<i class="fas fa-layer-group"></i>',
            "hub_title": "عزل الأسطح",
            "guide_title": "دليل عزل الأسطح",
            "guide_url": "",
            "links": "عزل مائي أم حراري |\nتحضير السطح قبل العزل |\nالضمان والصيانة |",
        },
        {
            "icon": '<i class="fas fa-droplet"></i>',
            "hub_title": "الرطوبة والفاتورة",
            "guide_title": "دليل الرطوبة وفاتورة المياه",
            "guide_url": "",
            "links": "ارتفاع فاتورة المياه |\nعفن الجدران والأسقف |\nالتجفيف بعد الإصلاح |",
        },
        {
            "icon": '<i class="fas fa-trowel-bricks"></i>',
            "hub_title": "الصيانة والترميم",
            "guide_title": "دليل صيانة المباني",
            "guide_url": "",
            "links": "معالجة الشروخ |\nترميم المنازل القديمة |\nبناء الملاحق |",
        },
        {
            "icon": '<i class="fas fa-hammer"></i>',
            "hub_title": "الحدادة والمظلات",
            "guide_title": "دليل الحدادة والمظلات",
            "guide_url": "",
            "links": "اختيار خامة الحديد |\nمظلات السيارات |\nالسواتر والبرجولات |",
        },
    ]
    return data


def patch_blog(meta: dict) -> dict:
    data = deepcopy(meta)
    data["title"] = "مقالات {%عن التسربات والعزل%}"
    data["content"] = "نصائح عملية عن كشف التسربات وعزل الأسطح ومعالجة الرطوبة والصيانة."
    return data


def patch_faq(meta: dict) -> dict:
    data = deepcopy(meta)
    data["content"] = "إجابات واضحة عن كشف التسربات والعزل والرطوبة وفاتورة المياه."
    data["manual_faqs"] = [
        {
            "question": "هل المعاينة مجانية؟",
            "answer": "نعم — زيارة الموقع ومعاينة التسرب أو السطح وأخذ المقاسات مجاناً داخل مناطق تغطيتنا، ثم تستلم عرض سعر مكتوب بدون التزام.",
            "category": "",
        },
        {
            "question": "متى أحتاج كشف تسربات المياه؟",
            "answer": "عند ارتفاع فاتورة المياه دون سبب، بقع رطوبة أو تقشير دهان، هبوط بلاط، رائحة عفن، أو بلل حول الخزان والمواسير. الكشف يحدّد المصدر قبل أي تكسير.",
            "category": "",
        },
        {
            "question": "هل تكسرون الأرضيات للوصول إلى التسرب؟",
            "answer": "لا نبدأ بالتكسير العشوائي. نستخدم أجهزة كشف لتحديد المنطقة بدقة، ثم نفتح فقط عند الحاجة للإصلاح.",
            "category": "",
        },
        {
            "question": "ماذا يشمل عزل الأسطح؟",
            "answer": "معاينة الميلان والتشققات، عزل مائي ضد الأمطار والرطوبة، وعزل حراري عند الحاجة لتقليل حرارة السطح. النوع والخامة يُحدَّدان بعد المعاينة ويُكتبان في العرض.",
            "category": "",
        },
        {
            "question": "هل ارتفاع فاتورة المياه يعني وجود تسرب؟",
            "answer": "غالباً نعم إذا لم يرتفع الاستهلاك الظاهر. نفحص العداد والخزان والمواسير المخفية ونوقف الهدر من مصدره بدل تخمين السبب.",
            "category": "",
        },
        {
            "question": "هل تعالجون الرطوبة أم تطْلون فوقها فقط؟",
            "answer": "نعالج المصدر أولاً (تسرب أو ضعف عزل)، ثم التجفيف، ثم الترميم والدهان حتى لا تعود الرطوبة.",
            "category": "",
        },
        {
            "question": "هل تقدّمون خدمات أخرى غير العزل والتسربات؟",
            "answer": "نعم — صيانة عامة وترميم، حدادة ومظلات وبرجولات، تشطيبات وأرضيات، سباكة وكهرباء وتكييف. التركيز الأول يبقى كشف التسربات والعزل.",
            "category": "",
        },
        {
            "question": "كيف أطلب الخدمة؟",
            "answer": "اتصل أو أرسل واتساب على 054 443 7175 ونحدد موعد المعاينة في موقعك.",
            "category": "",
        },
    ]
    return data


def patch_contact(meta: dict) -> dict:
    data = deepcopy(meta)
    data["title"] = "عندك تسرب أو {%سطح يحتاج عزل؟%}"
    data["content"] = (
        "ابدأ بكشف التسرب أو عزل السطح أو معالجة الرطوبة وارتفاع فاتورة المياه — "
        "وإن احتجت صيانة عامة أو حدادة فنحن نغطيها أيضاً. معاينة مجانية وعرض سعر مكتوب."
    )
    data["form_title"] = "احجز معاينة كشف أو عزل"
    return data


def patch_cta(meta: dict) -> dict:
    data = deepcopy(meta)
    title = "كشف تسرب أو عزل سطح؟ اطلب المعاينة"
    sub = "نصل لمعاينة التسرب والرطوبة والعزل، ونغطي بعدها الصيانة العامة وبقية الخدمات."
    data["section_title"] = title
    data["section_subtitle"] = sub
    data["cta_title"] = title
    data["cta_subtitle"] = sub
    return data


def patch_why_options() -> tuple[list, list]:
    steps = [
        {"num": "1", "title": "تواصل ومعاينة", "desc": "نحدد مصدر التسرب أو حاجة السطح للعزل."},
        {"num": "2", "title": "عرض سعر شفاف", "desc": "تكلفة واضحة للإصلاح أو العزل بدون مفاجآت."},
        {"num": "3", "title": "تنفيذ احترافي", "desc": "إصلاح المصدر ثم العزل أو الترميم."},
        {"num": "4", "title": "ضمان ومتابعة", "desc": "ضمان مكتوب ودعم بعد الخدمة."},
    ]
    features = [
        {"icon": "fas fa-magnifying-glass", "title": "كشف دقيق", "desc": "أجهزة تحدد التسرب دون تكسير عشوائي."},
        {"icon": "fas fa-layer-group", "title": "عزل متخصص", "desc": "عزل مائي وحراري بضمان مكتوب."},
        {"icon": "fas fa-droplet", "title": "معالجة رطوبة", "desc": "من المصدر لا من طلاء السطح فقط."},
        {"icon": "fas fa-file-invoice", "title": "وقف الهدر", "desc": "حل ارتفاع فاتورة المياه بعد الكشف."},
        {"icon": "fas fa-screwdriver-wrench", "title": "صيانة لاحقة", "desc": "حدادة ومظلات وتشطيبات من نفس الفريق."},
        {"icon": "fas fa-map-location-dot", "title": "تغطية واسعة", "desc": "خدمة في مدن الإمارات."},
    ]
    return steps, features


def find_hp_post(url: str, user: str, password: str, slug: str) -> int | None:
    data = cli(
        url,
        user,
        password,
        f"post list --s={slug} --post_status=draft,publish --post_type=post --fields=ID,post_title,post_status --format=json --posts_per_page=20",
    )
    raw = data.get("stdout") or "[]"
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(rows, list):
        return None
    for row in rows:
        title = (row.get("post_title") or "").strip()
        if title == slug:
            return int(row["ID"])
    return None


def ensure_hp_post(url: str, user: str, password: str, slug: str) -> int:
    existing = find_hp_post(url, user, password, slug)
    if existing:
        print("reuse clone", slug, existing)
        return existing
    created = cli(
        url,
        user,
        password,
        f"post create --post_title={slug} --post_status=draft --post_type=post",
        confirm=True,
    )
    log_cli(f"create {slug}", created)
    payload = json.loads(created.get("stdout") or "{}")
    pid = int(payload.get("ID") or 0)
    if not pid:
        raise RuntimeError(f"failed to create clone post {slug}")
    return pid


def write_widget_clone(
    url: str,
    user: str,
    password: str,
    *,
    source_id: int,
    slug: str,
    patch_fn,
    option_name: str,
    option_key: str,
) -> int:
    source = get_meta_json(url, user, password, source_id, "widget_post_meta")
    if not isinstance(source, dict):
        print("skip missing source meta", source_id)
        return 0
    clone_id = ensure_hp_post(url, user, password, slug)
    patched = patch_fn(source)
    encoded = json.dumps(json.dumps(patched, ensure_ascii=False))
    log_cli(
        f"meta {clone_id} {slug}",
        cli(
            url,
            user,
            password,
            f"post meta update {clone_id} widget_post_meta {encoded}",
            confirm=True,
        ),
    )
    log_cli(
        f"retarget {option_key}",
        cli(
            url,
            user,
            password,
            f"option patch update {option_name} {option_key} widget_post__id {clone_id}",
            confirm=True,
        ),
    )
    return clone_id


def main() -> int:
    url, user, password = config()
    widgets_only = "--widgets-only" in sys.argv
    print("update homepage focus: leaks + insulation first")

    if not widgets_only:
        intro = get_option_json(url, user, password, "HomeIntro")
        option_json(url, user, password, "HomeIntro", patch_home_intro(intro))

        steps, features = patch_why_options()
        option_json(url, user, password, "kayan_hp_why_steps", steps)
        option_json(url, user, password, "kayan_hp_why_features", features)

        blogdescription = (
            "شركة ماكس آرت لكشف تسربات المياه وعزل الأسطح ومعالجة الرطوبة "
            "وحل ارتفاع فاتورة المياه في الإمارات منذ 2008 — مع صيانة عامة وحدادة ومظلات. معاينة مجانية."
        )
        log_cli(
            "blogdescription",
            cli(
                url,
                user,
                password,
                "option update blogdescription " + json.dumps(blogdescription, ensure_ascii=False),
                confirm=True,
            ),
        )

        titles = get_option_json(url, user, password, "rank-math-options-titles")
        if isinstance(titles, dict):
            titles["homepage_title"] = "كشف تسربات المياه وعزل الأسطح | شركة ماكس آرت"
            titles["homepage_description"] = (
                "كشف تسربات المياه وعزل الأسطح ومعالجة الرطوبة وحل ارتفاع فاتورة المياه في الإمارات منذ 2008، "
                "مع صيانة عامة وحدادة ومظلات. معاينة مجانية."
            )
            option_json(url, user, password, "rank-math-options-titles", titles)

    clones = [
        (3591, "maxart-hp-finder", patch_finder, "1QsZmRLElt"),
        (3592, "maxart-hp-services", patch_services, "f2zweOA2b0"),
        (3593, "maxart-hp-benefits", patch_benefits, "D2da7xoDJh"),
        (3594, "maxart-hp-stats", patch_stats, "ZzedHTairS"),
        (3595, "maxart-hp-compare", patch_compare, "ZIyTaVE04x"),
        (3596, "maxart-hp-cities", patch_cities, "3t7DZz7KPs"),
        (3597, "maxart-hp-hub", patch_hub, "iGCbQHTBNq"),
        (3598, "maxart-hp-blog", patch_blog, "NCFHxS4dLJ"),
        (3599, "maxart-hp-faq", patch_faq, "xWzXP5kzM9"),
        (3600, "maxart-hp-contact", patch_contact, "pM7KwXZy6m"),
    ]
    for source_id, slug, fn, option_key in clones:
        write_widget_clone(
            url,
            user,
            password,
            source_id=source_id,
            slug=slug,
            patch_fn=fn,
            option_name="widgets_home__meta",
            option_key=option_key,
        )

    cta_source = get_meta_json(url, user, password, 3589, "widget_post_meta")
    if isinstance(cta_source, dict):
        cta_id = ensure_hp_post(url, user, password, "maxart-hp-cta")
        encoded = json.dumps(json.dumps(patch_cta(cta_source), ensure_ascii=False))
        log_cli(
            "meta cta",
            cli(url, user, password, f"post meta update {cta_id} widget_post_meta {encoded}", confirm=True),
        )
        order = get_option_json(url, user, password, "kayan_homepage_sections_order")
        if isinstance(order, dict):
            for section in order.get("sections") or []:
                if str(section.get("widget_post__id") or "") == "3589":
                    section["widget_post__id"] = str(cta_id)
            option_json(url, user, password, "kayan_homepage_sections_order", order)

    log_cli("purge", cli(url, user, password, "cache purge all", confirm=True))
    print("homepage focus update done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
