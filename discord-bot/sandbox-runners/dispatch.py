#!/usr/bin/env python3
"""
Unified dispatcher for sandbox skill runners.

Usage examples:
  python3 dispatch.py --skill playwright-mcp --action smoke --payload '{"url":"https://example.com"}'
  python3 dispatch.py --skill automation-workflows --action run --payload '{"workflowId":"smoke-test"}'
  python3 dispatch.py --skill agentmail --action send --payload '{"to":"eric@thesocial.study","subject":"Hi","templateId":"brief-v1"}'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

DEFAULT_ROUTES = {
    "playwright-mcp": {
        "url": "http://127.0.0.1:19081/run",
        "tokenEnv": "PLAYWRIGHT_RUNNER_TOKEN",
    },
    "playwright-scraper-skill": {
        "url": "http://127.0.0.1:19081/run",
        "tokenEnv": "PLAYWRIGHT_RUNNER_TOKEN",
    },
    "automation-workflows": {
        "url": "http://127.0.0.1:19082/run",
        "tokenEnv": "AUTOMATION_RUNNER_TOKEN",
    },
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dispatch one skill action to local sandbox runners")
    p.add_argument("--skill", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--payload", default="{}", help="JSON object payload")
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--routes", default="", help="Optional JSON file for route overrides")
    return p.parse_args()


def load_routes(path: str) -> dict:
    if not path:
        return DEFAULT_ROUTES
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("routes file must be a JSON object")
    merged = dict(DEFAULT_ROUTES)
    merged.update(data)
    return merged


def main() -> int:
    args = parse_args()

    try:
        payload = json.loads(args.payload)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "invalid_payload_json", "detail": str(e)}))
        return 2

    if not isinstance(payload, dict):
        print(json.dumps({"ok": False, "error": "payload_must_be_object"}))
        return 2

    try:
        routes = load_routes(args.routes)
    except Exception as e:
        print(json.dumps({"ok": False, "error": "invalid_routes_file", "detail": str(e)}))
        return 2

    route = routes.get(args.skill)
    if not route:
        print(json.dumps({"ok": False, "error": "skill_not_routed", "skill": args.skill}))
        return 3

    url = route.get("url")
    token_env = route.get("tokenEnv")
    token = os.getenv(token_env or "", "")

    if not url or not token_env:
        print(json.dumps({"ok": False, "error": "invalid_route_config", "skill": args.skill}))
        return 3

    if not token:
        print(json.dumps({"ok": False, "error": "missing_runner_token", "tokenEnv": token_env}))
        return 4

    body = json.dumps({"skill": args.skill, "action": args.action, "payload": payload}).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Runner-Token": token,
        },
    )

    try:
        with urlopen(req, timeout=max(2, min(args.timeout, 60))) as resp:
            out = resp.read().decode("utf-8", errors="replace")
            print(out)
            return 0
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        if raw:
            print(raw)
        else:
            print(json.dumps({"ok": False, "error": "http_error", "status": int(e.code)}))
        return 5
    except URLError as e:
        print(json.dumps({"ok": False, "error": "runner_unreachable", "detail": str(e.reason)}))
        return 6
    except Exception as e:
        print(json.dumps({"ok": False, "error": "dispatch_failed", "detail": str(e)}))
        return 7


if __name__ == "__main__":
    sys.exit(main())
