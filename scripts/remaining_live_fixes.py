#!/usr/bin/env python3
"""Remaining live Max Art repairs after the content-quality pass.

Fixes Rank Math noindex format, homepage 34/5415 claims, dummy 0500000000,
personal social URLs, /en/ redirect priority, and About copy.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import PHONE_DISPLAY, cli, config, log_cli, request  # noqa: E402
from fix_content_quality import ABOUT, update_post  # noqa: E402

PHONE_FAKE = "0500000000"
PHONE_REAL = "0544437175"


def meta_json(url, user, password, pid: int, key: str, value) -> None:
    encoded = json.dumps(json.dumps(value, ensure_ascii=False))
    log_cli(
        f"meta {pid} {key}",
        cli(
            url,
            user,
            password,
            f"post meta update {pid} {key} {encoded} --format=json --force",
            confirm=True,
        ),
    )


def option_json(url, user, password, name: str, value) -> None:
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


def get_meta_json(url, user, password, pid: int, key: str):
    raw = cli(url, user, password, f"post meta get {pid} {key} --format=json").get("stdout") or "null"
    return json.loads(raw)


def get_option_json(url, user, password, name: str):
    raw = cli(url, user, password, f"option get {name} --format=json").get("stdout") or "null"
    return json.loads(raw)


def content_edit(url, user, password, payload: dict) -> int:
    try:
        data = request(
            f"{url}/wp-json/wpvibe/v1/content/edit",
            user,
            password,
            method="POST",
            payload=payload,
            timeout=45,
        )
        return int((data or {}).get("replaced") or 0)
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if "HTTP 422" in msg or "no_match" in msg:
            return 0
        print("content_edit fail", payload.get("post_id") or payload.get("option_name"), msg[:220])
        return 0


def same_len(old: str, new: str) -> None:
    if len(old.encode("utf-8")) != len(new.encode("utf-8")):
        raise ValueError(f"byte length mismatch {old!r} ({len(old.encode('utf-8'))}) vs {new!r} ({len(new.encode('utf-8'))})")


def patch_serialized(url, user, password, *, post_id=None, option_name=None, meta_key=None, pairs: list[tuple[str, str]]) -> None:
    for old, new in pairs:
        same_len(old, new)
        payload = {"old_content": old, "new_content": new, "replace_all": True}
        if option_name:
            payload.update({"target_type": "option", "option_name": option_name})
        else:
            payload.update({"target_type": "meta", "post_id": post_id, "meta_key": meta_key})
        n = content_edit(url, user, password, payload)
        print("replaced", old, "->", new, "n=", n, "on", post_id or option_name)


def patch_widgets(url, user, password) -> None:
    # Same UTF-8 byte length so PHP serialized s:N: stays valid if the editor is naive.
    pairs = [("34 خدمة", "10 خدمة"), ("5415", "10  ")]
    for pid in (3592, 3593, 3594, 3595, 3596):
        patch_serialized(url, user, password, post_id=pid, meta_key="widget_post_meta", pairs=pairs)


def patch_home_intro(url, user, password) -> None:
    patch_serialized(url, user, password, option_name="HomeIntro", pairs=[("5415", "10  ")])
    patch_serialized(
        url,
        user,
        password,
        option_name="kayan_hp_stats_items",
        pairs=[("500", "10 ")],
    )


def fix_robots(url, user, password) -> None:
    raw = cli(
        url,
        user,
        password,
        """db query "SELECT post_id FROM wpt0_postmeta WHERE meta_key='rank_math_robots' AND meta_value LIKE '%noindex%'" --skip-column-names""",
    )
    payload = json.loads(raw.get("stdout") or "{}")
    ids = [int(r["post_id"]) for r in payload.get("results") or []]
    print("reapply noindex", len(ids))
    robots = ["noindex", "follow"]
    for i, pid in enumerate(ids, 1):
        try:
            meta_json(url, user, password, pid, "rank_math_robots", robots)
        except Exception as exc:  # noqa: BLE001
            print("robots fail", pid, exc)
        if i % 25 == 0:
            print("robots progress", i, "/", len(ids), flush=True)
        time.sleep(0.03)


def fix_dummy_phones(url, user, password) -> None:
    raw = cli(
        url,
        user,
        password,
        f"""db query "SELECT ID FROM wpt0_posts WHERE post_status='publish' AND (post_content LIKE '%{PHONE_FAKE}%' OR post_excerpt LIKE '%{PHONE_FAKE}%')" --skip-column-names""",
    )
    payload = json.loads(raw.get("stdout") or "{}")
    ids = [int(r["ID"]) for r in payload.get("results") or []]
    print("dummy phone posts", len(ids))
    total = 0
    for pid in ids:
        total += content_edit(
            url,
            user,
            password,
            {
                "target_type": "post",
                "post_id": pid,
                "field": "post_content",
                "old_content": PHONE_FAKE,
                "new_content": PHONE_REAL,
                "replace_all": True,
            },
        )
        total += content_edit(
            url,
            user,
            password,
            {
                "target_type": "post",
                "post_id": pid,
                "field": "post_excerpt",
                "old_content": PHONE_FAKE,
                "new_content": PHONE_REAL,
                "replace_all": True,
            },
        )
    print("dummy phone replacements", total)


def fix_en_redirect(url, user, password) -> None:
    print("draft theme")
    draft = request(f"{url}/wp-json/wpvibe/v1/draft-theme", user, password, method="POST", payload={})
    print("draft", json.dumps(draft, ensure_ascii=False)[:400] if isinstance(draft, dict) else draft)
    edited = request(
        f"{url}/wp-json/wpvibe/v1/file/edit",
        user,
        password,
        method="POST",
        payload={
            "path": "functions.php",
            "old_content": "add_action( 'template_redirect', 'maxart_redirect_foreign_prefixes', 0 );",
            "new_content": "add_action( 'template_redirect', 'maxart_redirect_foreign_prefixes', -1 );",
        },
    )
    print("edit", edited)
    pub = request(f"{url}/wp-json/wpvibe/v1/draft-theme/publish", user, password, method="POST", payload={})
    print("publish", json.dumps(pub, ensure_ascii=False)[:500] if isinstance(pub, dict) else pub)


def main() -> int:
    url, user, password = config()
    print("remaining live fixes")

    update_post(url, user, password, 4034, content=ABOUT, excerpt="ماكس آرت: حدادة، مظلات، عزل وكشف تسربات منذ 2008.")

    print("widgets + intro")
    patch_widgets(url, user, password)
    patch_home_intro(url, user, password)

    print("social empty (do not invent company accounts)")
    for opt in ("facebook", "instagram", "twitter"):
        log_cli(opt, cli(url, user, password, f'option update {opt} ""', confirm=True))

    print("dummy phones")
    fix_dummy_phones(url, user, password)

    print("rank math robots")
    fix_robots(url, user, password)

    print("en redirect priority")
    try:
        fix_en_redirect(url, user, password)
    except Exception as exc:  # noqa: BLE001
        print("theme edit failed", exc)

    log_cli("purge", cli(url, user, password, "cache purge all", confirm=True))
    print("remaining done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
