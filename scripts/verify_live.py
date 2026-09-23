#!/usr/bin/env python3
"""Verify live Max Art URLs after content-quality repairs. No secrets printed."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import cli, config, rest  # noqa: E402

UA = "max-art-ae-verify/1.0"


def fetch(url: str, method: str = "GET") -> tuple[int, dict[str, str], str]:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, body


def snippet(html: str, needle: str, width: int = 80) -> str:
    i = html.find(needle)
    if i < 0:
        return "NOT FOUND"
    start = max(0, i - 40)
    return html[start : i + width].replace("\n", " ")


def main() -> int:
    url, user, password = config()
    print("=== HTTP checks ===")
    urls = [
        "https://max-art-ae.com/",
        "https://max-art-ae.com/about-us/",
        "https://max-art-ae.com/contact-us/",
        "https://max-art-ae.com/services/",
        "https://max-art-ae.com/services/leak-detection/",
        "https://max-art-ae.com/services/roof-insulation/",
        "https://max-art-ae.com/services/blacksmith/",
        "https://max-art-ae.com/services/umbrellas-shutters/",
        "https://max-art-ae.com/services/electrical/",
        "https://max-art-ae.com/services/plumbing/",
        "https://max-art-ae.com/services/painting/",
        "https://max-art-ae.com/services/ac-maintenance/",
        "https://max-art-ae.com/services/gas-leak-detection/",
        "https://max-art-ae.com/services/building-maintenance/",
        "https://max-art-ae.com/this-page-does-not-exist-audit-404/",
        "https://max-art-ae.com/mpg_citys-expert-plumbing-services/",
        "https://max-art-ae.com/en/",
        "https://max-art-ae.com/sa/",
        "https://max-art-ae.com/robots.txt",
        "https://max-art-ae.com/sitemap_index.xml",
        "https://max-art-ae.com/page-sitemap.xml",
        "https://max-art-ae.com/services-sitemap.xml",
    ]
    for u in urls:
        code, headers, body = fetch(u)
        loc = headers.get("location", "")
        flags = []
        low = body.lower()
        if "noindex" in low:
            flags.append("noindex-in-html")
        if 'rel="canonical"' in low or "rel='canonical'" in low:
            flags.append("canonical")
        if "fatal error" in low or "كان هناك خطأ فادح" in body:
            flags.append("FATAL")
        if "34" in body and "خدمة" in body:
            flags.append("claims-34")
        print(f"{code:3} {u} loc={loc[:80]} {' '.join(flags)} bytes={len(body)}")

    print("\n=== clone robots sample ===")
    # a known clone from audit
    sample = "https://max-art-ae.com/sharikat-aslah-tasrib-almyah-fi-alnaymyh/"
    code, headers, body = fetch(sample)
    robots = ""
    canon = ""
    for line in body.splitlines():
        if "robots" in line.lower() and "name=" in line.lower():
            robots = line.strip()[:200]
        if "canonical" in line.lower() and "rel=" in line.lower():
            canon = line.strip()[:250]
    print("status", code)
    print("robots meta", robots or snippet(body, "robots"))
    print("canonical", canon or snippet(body, "canonical"))

    print("\n=== REST counts ===")
    for path, label in (
        ("/wp/v2/services?per_page=50", "services"),
        ("/wp/v2/pages?per_page=50", "pages"),
        ("/wp/v2/posts?per_page=1", "posts"),
    ):
        data = rest(url, user, password, path)
        if isinstance(data, list):
            print(label, len(data), [x.get("slug") for x in data][:20] if label != "posts" else "...")
        else:
            print(label, type(data), str(data)[:200])

    svcs = rest(url, user, password, "/wp/v2/services?per_page=50")
    print("\n=== service word-ish lengths ===")
    for s in svcs or []:
        raw = s.get("content", {}).get("rendered") or ""
        text = " ".join(raw.split())
        print(s.get("id"), s.get("slug"), "chars", len(text), s.get("link"))

    print("\n=== WP-CLI meta samples ===")
    for pid in (2940, 3317, 4034, 4035, 4835, 3262, 2612):
        robots_m = cli(url, user, password, f"post meta get {pid} rank_math_robots")
        canon_m = cli(url, user, password, f"post meta get {pid} rank_math_canonical_url")
        status = cli(url, user, password, f"post get {pid} --field=post_status")
        print(
            pid,
            "status=",
            (status.get("stdout") or "").strip(),
            "robots=",
            (robots_m.get("stdout") or "").strip()[:80],
            "canon=",
            (canon_m.get("stdout") or "").strip()[:80],
        )

    print("\n=== leftover identity ===")
    for term in ("97431110184", "ركن التطور", "خالد المطيري"):
        r = cli(url, user, password, f'db query "SELECT ID, post_title FROM wpt0_posts WHERE post_status=\'publish\' AND post_content LIKE \'%{term}%\' LIMIT 5" --skip-column-names')
        print(term, (r.get("stdout") or "").strip()[:300] or "none")

    print("\n=== homepage 34 / footer ===")
    code, _, home = fetch("https://max-art-ae.com/")
    print("home", code, "34 خدمة" in home, "data-count" in home)
    for n in ("34", "5415", "blacksmith", "umbrellas-shutters", "contact-us"):
        print(" ", n, home.count(n) if n.isdigit() else (n in home))

    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
