#!/usr/bin/env python3
"""Merge daily ledger indexes into a weekly searchable index (JSONL).

Inputs:
- ~/.openclaw/workspace/vault/ledger/YYYY-MM-DD.index.jsonl

Output:
- ~/.openclaw/workspace/vault/ledger_weekly/YYYY-Www.index.jsonl

Why JSONL?
- Fast grep.
- Easy to parse later (jq/python).

This is local-only and does not call external services.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/Los_Angeles"


def iso_week_id(d: dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_start(d: dt.date) -> dt.date:
    # ISO week starts Monday
    return d - dt.timedelta(days=d.isoweekday() - 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tz", default=DEFAULT_TZ)
    ap.add_argument(
        "--week",
        help="ISO week id like YYYY-Www (default: current week in tz)",
    )
    ap.add_argument(
        "--outdir",
        default=os.path.expanduser("~/.openclaw/workspace/vault/ledger_weekly"),
    )
    ap.add_argument(
        "--ledgerdir",
        default=os.path.expanduser("~/.openclaw/workspace/vault/ledger"),
    )
    args = ap.parse_args()

    tz = ZoneInfo(args.tz)
    today = dt.datetime.now(tz).date()

    if args.week:
        week_id = args.week
        y = int(week_id.split("-W")[0])
        w = int(week_id.split("-W")[1])
        # Find Monday of that ISO week.
        # ISO calendar: week 1 is the one containing Jan 4.
        jan4 = dt.date(y, 1, 4)
        start = week_start(jan4) + dt.timedelta(weeks=w - 1)
    else:
        start = week_start(today)
        week_id = iso_week_id(today)

    end = start + dt.timedelta(days=7)

    # Collect daily index files within [start, end)
    paths: list[str] = []
    for day in (start + dt.timedelta(days=i) for i in range(7)):
        p = os.path.join(args.ledgerdir, f"{day.isoformat()}.index.jsonl")
        if os.path.exists(p):
            paths.append(p)

    os.makedirs(args.outdir, exist_ok=True)
    outpath = os.path.join(args.outdir, f"{week_id}.index.jsonl")

    rows = []
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                obj["week"] = week_id
                obj["day"] = os.path.basename(p).split(".")[0]  # YYYY-MM-DD
                rows.append(obj)

    rows.sort(key=lambda r: r.get("ts") or "")

    with open(outpath, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(outpath)


if __name__ == "__main__":
    main()
