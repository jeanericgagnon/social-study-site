#!/usr/bin/env python3
"""Export a daily, searchable ledger of Eric <-> Sys communications.

Goal: make our chat history *searchable on disk*.

Sources (local-only):
- OpenClaw session transcript JSONL files under:
  ~/.openclaw/agents/**/sessions/*.jsonl

Outputs (local-only):
- Markdown: ~/.openclaw/workspace/vault/ledger/YYYY-MM-DD.md
- Search index (JSONL): ~/.openclaw/workspace/vault/ledger/YYYY-MM-DD.index.jsonl

Notes:
- Intentionally simple/robust: no cloud APIs.
- Captures ONLY message.role in {user, assistant}.
- Scans *all* transcript files, not just the latest, so it survives restarts/new sessions.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


DEFAULT_TZ = "America/Los_Angeles"


@dataclass
class Msg:
    ts: dt.datetime
    role: str
    text: str
    msg_id: str | None


def _find_transcripts() -> list[str]:
    candidates = glob.glob(os.path.expanduser("~/.openclaw/agents/**/sessions/*.jsonl"), recursive=True)
    if not candidates:
        raise SystemExit("No transcript JSONL files found under ~/.openclaw/agents/**/sessions/")
    # Stable ordering (newest last makes debugging easier).
    candidates.sort(key=lambda p: os.path.getmtime(p))
    return candidates


def _iter_messages(path: str):
    session_id = os.path.splitext(os.path.basename(path))[0]
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "message":
                continue
            m = obj.get("message") or {}
            role = m.get("role")
            if role not in ("user", "assistant"):
                continue

            # Timestamp is on the wrapper.
            ts_raw = obj.get("timestamp")
            if not ts_raw:
                continue
            try:
                ts = dt.datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except Exception:
                continue

            # Extract plain text content.
            content = m.get("content") or []
            parts: list[str] = []
            for c in content:
                ctype = c.get("type")
                if ctype == "text":
                    parts.append(c.get("text") or "")
                # Intentionally skip tool calls, thinking, images, etc.
            text = "".join(parts).strip()
            if not text:
                continue

            # We'll store the session id in msg_id prefix for debugging/search.
            msg_id = m.get("id") or obj.get("id")
            if msg_id and not msg_id.startswith(session_id):
                msg_id = f"{session_id}:{msg_id}"

            yield Msg(ts=ts, role=role, text=text, msg_id=msg_id)


def _md_escape(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Local date to export (YYYY-MM-DD). Default: today.")
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"Timezone (default {DEFAULT_TZ}).")
    ap.add_argument(
        "--transcript",
        action="append",
        help="Path to transcript JSONL (repeatable). Default: scan all under ~/.openclaw/agents/**/sessions/*.jsonl",
    )
    ap.add_argument("--outdir", default=os.path.expanduser("~/.openclaw/workspace/vault/ledger"))
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)

    if args.date:
        day = dt.date.fromisoformat(args.date)
    else:
        day = dt.datetime.now(tz).date()

    start_local = dt.datetime.combine(day, dt.time.min, tzinfo=tz)
    end_local = start_local + dt.timedelta(days=1)

    transcripts = args.transcript if args.transcript else _find_transcripts()

    msgs: list[Msg] = []
    used_transcripts: set[str] = set()
    for tpath in transcripts:
        for m in _iter_messages(tpath):
            local_ts = m.ts.astimezone(tz)
            if start_local <= local_ts < end_local:
                used_transcripts.add(tpath)
                msgs.append(Msg(ts=local_ts, role=m.role, text=m.text, msg_id=m.msg_id))

    msgs.sort(key=lambda m: m.ts)

    os.makedirs(args.outdir, exist_ok=True)
    out_md = os.path.join(args.outdir, f"{day.isoformat()}.md")
    out_idx = os.path.join(args.outdir, f"{day.isoformat()}.index.jsonl")

    lines: list[str] = []
    lines.append(f"# Ledger — {day.isoformat()} ({args.tz})")
    lines.append("")
    if used_transcripts:
        lines.append("Sources:")
        for p in sorted(used_transcripts):
            lines.append(f"- `{p}`")
    else:
        lines.append("Sources: (none matched date range)")
    lines.append(f"Range: {start_local.isoformat()} → {end_local.isoformat()}")
    lines.append("")
    lines.append("## Highlights (manual or future automation)")
    lines.append("- (empty)")
    lines.append("")
    lines.append("## Full conversation")
    lines.append("")

    if not msgs:
        lines.append("(No messages captured for this date.)")
    else:
        for m in msgs:
            stamp = m.ts.strftime("%H:%M:%S")
            who = "Eric" if m.role == "user" else "Sys"
            lines.append(f"### {stamp} — {who}")
            lines.append("")
            lines.append(_md_escape(m.text))
            lines.append("")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    # Write a daily JSONL index for grep/jq tooling.
    with open(out_idx, "w", encoding="utf-8") as f:
        for m in msgs:
            f.write(
                json.dumps(
                    {
                        "ts": m.ts.isoformat(),
                        "role": m.role,
                        "who": "Eric" if m.role == "user" else "Sys",
                        "id": m.msg_id,
                        "text": m.text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(out_md)


if __name__ == "__main__":
    main()
