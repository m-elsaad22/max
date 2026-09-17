#!/usr/bin/env python3
"""Connect to max-art-ae.com via WordPress REST + WPVibe.

Reads WP_URL, WP_USER, and WP_APP_PASSWORD from the environment or a local .env file.
Does not print the application password.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "https://max-art-ae.com"
USER_AGENT = "max-art-ae-cursor-connect/1.0"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def config() -> tuple[str, str, str]:
    load_dotenv(ROOT / ".env")
    url = os.environ.get("WP_URL", DEFAULT_URL).rstrip("/")
    user = os.environ.get("WP_USER", "").strip()
    password = os.environ.get("WP_APP_PASSWORD", "").strip()
    if not user or not password:
        sys.exit(
            "Missing WP_USER or WP_APP_PASSWORD. Copy .env.example to .env and set the application password."
        )
    return url, user, password


def request(url: str, user: str, password: str, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {
        "Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode(),
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(detail)
            detail = json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        raise SystemExit(f"HTTP {exc.code} {method} {url}\n{detail}") from exc


def cmd_status(url: str, user: str, password: str) -> int:
    ping = request(f"{url}/wp-json/wpvibe/v1/ping", user, password)
    me = request(f"{url}/wp-json/wp/v2/users/me?context=edit", user, password)
    info = request(f"{url}/wp-json/wpvibe/v1/site-info", user, password)
    theme = (info or {}).get("active_theme") or {}
    print("connection: ok")
    print(f"site:       {(info or {}).get('site_name')} ({url})")
    print(f"wordpress:  {(info or {}).get('wp_version')}  php {(info or {}).get('php_version')}")
    print(f"wpvibe:     {(ping or {}).get('plugin_version')}")
    print(f"user:       {me.get('username')}  roles={','.join(me.get('roles') or [])}")
    print(f"theme:      {theme.get('name')} ({theme.get('stylesheet')} v{theme.get('version')})")
    print(f"wp-cli:     {(info or {}).get('wp_cli_available')}")
    print(f"mcp:        {url}/wp-json/mcp/mcp-adapter-default-server")
    return 0


def cmd_get(url: str, user: str, password: str, path: str) -> int:
    if not path.startswith("/"):
        path = "/" + path
    if path.startswith("/wp-json"):
        target = f"{url}{path}"
    else:
        target = f"{url}/wp-json{path}"
    data = request(target, user, password)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_cli(url: str, user: str, password: str, command: str) -> int:
    data = request(
        f"{url}/wp-json/wpvibe/v1/cli/run",
        user,
        password,
        method="POST",
        payload={"command": command},
    )
    stdout = (data or {}).get("stdout") or ""
    stderr = (data or {}).get("stderr") or ""
    if stdout:
        sys.stdout.write(stdout if stdout.endswith("\n") else stdout + "\n")
    if stderr:
        sys.stderr.write(stderr if stderr.endswith("\n") else stderr + "\n")
    return int((data or {}).get("exit_code") or 0)


def cmd_files(url: str, user: str, password: str, directory: str, scope: str) -> int:
    query = urllib.parse.urlencode({"scope": scope, "directory": directory})
    data = request(f"{url}/wp-json/wpvibe/v1/file/list?{query}", user, password)
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Connect to the Max Art WordPress site")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Verify application-password authentication")
    get_p = sub.add_parser("get", help="GET a wp-json path, e.g. /wp/v2/pages")
    get_p.add_argument("path")
    cli_p = sub.add_parser("cli", help="Run a WP-CLI command through WPVibe")
    cli_p.add_argument("wp_command")
    files_p = sub.add_parser("files", help="List theme or wp-content files through WPVibe")
    files_p.add_argument("--directory", default="")
    files_p.add_argument("--scope", default="theme", choices=("theme", "wp-content"))

    args = parser.parse_args()
    url, user, password = config()
    if args.command == "status":
        return cmd_status(url, user, password)
    if args.command == "get":
        return cmd_get(url, user, password, args.path)
    if args.command == "cli":
        return cmd_cli(url, user, password, args.wp_command)
    if args.command == "files":
        return cmd_files(url, user, password, args.directory, args.scope)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
