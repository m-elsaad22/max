#!/usr/bin/env python3
"""Replace Qatar phones and Rukn/Khalid strings via WPVibe content/edit."""

from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_live_fixes import cli, config, request  # noqa: E402

REPLACEMENTS = (
    ("97431110184", "971544437175"),
    ("97431553076", "971544437175"),
    ("خالد المطيري", "فريق ماكس آرت"),
    ("ركن التطور", "ماكس آرت"),
    ("شهادة ISO 9001", "ضمان مكتوب"),
)


def fetch_ids(url: str, user: str, password: str) -> list[int]:
    data = cli(
        url,
        user,
        password,
        """db query "SELECT ID FROM wpt0_posts WHERE post_status IN ('publish','draft','private') AND post_type IN ('post','price','page','services') AND (post_content LIKE '%97431110184%' OR post_content LIKE '%97431553076%' OR post_content LIKE '%خالد المطيري%' OR post_content LIKE '%ركن التطور%')" --limit=500""",
    )
    payload = json.loads(data.get("stdout") or "{}")
    return [int(r["ID"]) for r in payload.get("results") or []]


def edit_post(url: str, user: str, password: str, pid: int) -> tuple[int, int, str]:
    replaced = 0
    last = "ok"
    for old, new in REPLACEMENTS:
        for attempt in range(4):
            try:
                data = request(
                    f"{url}/wp-json/wpvibe/v1/content/edit",
                    user,
                    password,
                    method="POST",
                    payload={
                        "target_type": "post",
                        "post_id": pid,
                        "field": "post_content",
                        "old_content": old,
                        "new_content": new,
                        "replace_all": True,
                    },
                    timeout=45,
                )
                replaced += int((data or {}).get("replaced") or 0)
                last = "ok"
                break
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                if "HTTP 422" in msg or "no_match" in msg or ("HTTP 404" in msg and "not_found" in msg):
                    last = "ok"
                    break
                last = msg[:120]
                time.sleep(1.2 * (attempt + 1))
        else:
            return pid, replaced, last
    return pid, replaced, last


def main() -> int:
    url, user, password = config()
    ids = fetch_ids(url, user, password)
    print(f"to_update {len(ids)}", flush=True)
    ok = fail = total_repl = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = {pool.submit(edit_post, url, user, password, pid): pid for pid in ids}
        done = 0
        for fut in as_completed(futs):
            pid, replaced, status = fut.result()
            done += 1
            total_repl += replaced
            if status == "ok" or status == "skip":
                ok += 1
            else:
                fail += 1
                print(f"FAIL {pid} {status}", flush=True)
            if done % 15 == 0 or done == len(ids):
                print(f"progress {done}/{len(ids)} ok={ok} fail={fail} replacements={total_repl}", flush=True)
    print(f"done ok={ok} fail={fail} replacements={total_repl}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
