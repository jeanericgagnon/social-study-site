#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
from pathlib import Path

LOG_PATH = Path.home() / ".openclaw" / "logs" / "gateway.log"
STATE_PATH = Path.home() / ".openclaw" / "workspace" / "ops" / "error-watcher-state.json"
COOLDOWN_SECONDS = 15 * 60
WINDOW_SECONDS = 10 * 60
OPENCLAW_BIN = "/opt/homebrew/bin/openclaw"

PATTERNS = [
    re.compile(r"health-monitor: restarting \(reason: (?P<reason>[^\)]+)\)"),
    re.compile(r"gateway: WebSocket connection closed with code (?P<code>\d+)"),
    re.compile(r"\berrorCode=(?P<error>[A-Z_]+)\b"),
]


def load_state():
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    return {}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


def send_alert(text):
    subprocess.run(
        [OPENCLAW_BIN, "system", "event", "--mode", "now", "--text", text],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def classify(line):
    lower = line.lower()
    provider = "unknown"
    if "[discord" in lower:
        provider = "discord"
    elif "[imessage" in lower:
        provider = "imessage"
    elif "[whatsapp" in lower:
        provider = "whatsapp"

    for pat in PATTERNS:
        m = pat.search(line)
        if m:
            data = m.groupdict()
            if "reason" in data and data["reason"]:
                return provider, f"restart:{data['reason']}"
            if "code" in data and data["code"]:
                return provider, f"ws-close:{data['code']}"
            if "error" in data and data["error"]:
                return provider, f"error:{data['error']}"
    return None, None


def tail_follow(path: Path):
    while not path.exists():
        time.sleep(2)
    with path.open("r", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.4)
                continue
            yield line.rstrip("\n")


def main():
    state = load_state()
    now = int(time.time())

    state.setdefault("lastAlertAt", {})
    state.setdefault("recent", {})

    for line in tail_follow(LOG_PATH):
        provider, event = classify(line)
        if not event:
            continue

        key = f"{provider}:{event}"
        now = int(time.time())

        rec = state["recent"].setdefault(key, [])
        rec.append(now)
        state["recent"][key] = [t for t in rec if now - t <= WINDOW_SECONDS]

        last_alert = state["lastAlertAt"].get(key, 0)
        if now - last_alert < COOLDOWN_SECONDS:
            save_state(state)
            continue

        count = len(state["recent"][key])
        text = (
            f"Auto-triage alert: {provider} {event} occurred {count} times in the last "
            f"{WINDOW_SECONDS // 60}m. Check logs if this repeats."
        )
        send_alert(text)
        state["lastAlertAt"][key] = now
        save_state(state)


if __name__ == "__main__":
    main()
