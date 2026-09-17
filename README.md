# ماكس آرت — max-art-ae.com

مستودع ربط Cursor بموقع [شركة ماكس آرت](https://max-art-ae.com) عبر واجهة ووردبريس وكلمة مرور التطبيقات.

كلمة المرور **لا تُحفظ في Git**. ضعها محلياً في ملف `.env` (انظر `.env.example`).

## حالة الاتصال

تم التحقق من الاتصال بحساب المسؤول `mahmoud` عبر WordPress REST وWPVibe:

| البند | القيمة |
| --- | --- |
| الموقع | https://max-art-ae.com |
| ووردبريس | 7.1 / PHP 8.3.19 |
| القالب النشط | KAYAN Theme `kayan-theme` 2.4.7 |
| إضافة الربط | WPVibe 1.17.0 |
| اللغة | العربية |
| مقالات | 315 |
| صفحات منشورة | سياسة الخصوصية، المدونة، من نحن، تواصل معنا |
| خدمات CPT | 10 (حدادة، مظلات، عزل، كشف تسربات، كهرباء، سباكة، دهانات، تكييف، غاز، صيانة مباني) |

لقطة أوفى في [`site/inventory.json`](site/inventory.json).

تقرير الفحص التفصيلي (أخطاء ونواقص الموقع والقالب): [`site/AUDIT.md`](site/AUDIT.md).

تدقيق المحتوى وSEO لكل العناصر المنشورة: [`site/SEO_CONTENT_AUDIT.md`](site/SEO_CONTENT_AUDIT.md) و[`site/seo-content-audit.csv`](site/seo-content-audit.csv).

```bash
python3 scripts/seo_content_audit.py
python3 scripts/fix_content_quality.py   # ركائز + خدمات + noindex للنسخ
python3 scripts/remaining_live_fixes.py  # 34 خدمة، هواتف وهمية، noindex Rank Math
python3 scripts/verify_live.py
python3 scripts/phase2_cleanup.py          # dry-run only
python3 scripts/phase2_cleanup.py --execute  # after explicit approval
```

إصلاحات 17 سبتمبر 2026 موثّقة في [`site/AUDIT.md`](site/AUDIT.md) القسم (م) و[`site/SEO_CONTENT_AUDIT.md`](site/SEO_CONTENT_AUDIT.md).

## الاستخدام

```bash
cp .env.example .env
# حرّر .env وضع كلمة مرور التطبيقات في WP_APP_PASSWORD

python3 scripts/wp_connect.py status
python3 scripts/wp_connect.py get /wp/v2/pages
python3 scripts/wp_connect.py cli 'plugin list --status=active'
python3 scripts/phase2_cleanup.py
```

Phase 2 (JSON-LD strip, featured-image diversification, local sitemap/plugin delete) is **dry-run by default**. It does not write or delete until `--execute` is passed. Task 1 needs `WP_ROOT` set to the live WordPress document root on the server; this repository is not that tree.

نقاط النهاية:

- REST: `https://max-art-ae.com/wp-json/`
- WPVibe: `https://max-art-ae.com/wp-json/wpvibe/v1/`
- MCP: `https://max-art-ae.com/wp-json/mcp/mcp-adapter-default-server`

القالب المصدري: [m-elsaad22/Kayan-Theme](https://github.com/m-elsaad22/Kayan-Theme).
