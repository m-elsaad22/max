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
| صفحات | 3 |
| خدمات CPT | 2 |

لقطة أوفى في [`site/inventory.json`](site/inventory.json).

تقرير الفحص التفصيلي (أخطاء ونواقص الموقع والقالب): [`site/AUDIT.md`](site/AUDIT.md).

## الاستخدام

```bash
cp .env.example .env
# حرّر .env وضع كلمة مرور التطبيقات في WP_APP_PASSWORD

python3 scripts/wp_connect.py status
python3 scripts/wp_connect.py get /wp/v2/pages
python3 scripts/wp_connect.py cli 'plugin list --status=active'
```

نقاط النهاية:

- REST: `https://max-art-ae.com/wp-json/`
- WPVibe: `https://max-art-ae.com/wp-json/wpvibe/v1/`
- MCP: `https://max-art-ae.com/wp-json/mcp/mcp-adapter-default-server`

القالب المصدري: [m-elsaad22/Kayan-Theme](https://github.com/m-elsaad22/Kayan-Theme).
