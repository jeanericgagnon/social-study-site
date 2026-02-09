#!/usr/bin/env python3
"""Ingest customer complaint emails from Sys Gmail and append summaries to a Google Sheet.

- Gmail access: read-only.
- Sheets access: write.
- De-dup: stores processed Gmail message IDs in memory/complaints_processed.json

Usage:
  .venv/bin/python scripts/complaints_ingest.py --spreadsheet <ID> \
    --query 'to:clawsystss@gmail.com subject:(complaint)'

Recommended query examples:
  --query 'from:quino@thesocial.study'
  --query 'to:clawsystss@gmail.com (complaint OR refund OR cancel OR angry OR upset)'

"""

import argparse
import base64
import datetime as dt
import json
import re
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

HERE = Path(__file__).resolve().parents[1]
TOKEN_PATH = HERE / "gcal" / "token_sys.json"
PROCESSED_PATH = HERE / "memory" / "complaints_processed.json"

DEFAULT_HEADERS = [
    [
        "ReceivedAt",
        "From",
        "Subject",
        "City",
        "Venue",
        "Category",
        "Urgency",
        "Summary",
        "RecommendedAction",
        "Status",
        "GmailMessageId",
        "ThreadId",
        "Permalink",
    ]
]


def load_creds() -> Credentials:
    data = json.loads(TOKEN_PATH.read_text())
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        TOKEN_PATH.write_text(json.dumps(data, indent=2))
    return creds


def decode_b64url(s: str) -> str:
    return base64.urlsafe_b64decode(s.encode("utf-8")).decode("utf-8", errors="replace")


def extract_text(payload: dict) -> str:
    """Extract first text/plain part; fallback to any text/* body."""

    def walk(part: dict) -> str:
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data and mime == "text/plain":
            return decode_b64url(data)
        for p in part.get("parts", []) or []:
            t = walk(p)
            if t:
                return t
        if data and mime.startswith("text/"):
            return decode_b64url(data)
        return ""

    return walk(payload) or ""


def hdr(headers: list, name: str) -> str:
    for h in headers:
        if (h.get("name", "").lower()) == name.lower():
            return h.get("value", "")
    return ""


def clean_text(s: str) -> str:
    s = re.sub(r"\r\n?", "\n", s)
    # strip common reply separators
    s = re.split(r"\nOn .*wrote:\n", s, maxsplit=1)[0]
    s = re.split(r"\nFrom: .*\nSent: .*\nTo: .*\nSubject: ", s, maxsplit=1)[0]
    s = re.sub(r"\s+", " ", s).strip()
    return s


def naive_summary(body: str, limit: int = 500) -> str:
    body = clean_text(body)
    if not body:
        return ""
    return body[:limit] + ("…" if len(body) > limit else "")


def load_processed() -> set:
    if not PROCESSED_PATH.exists():
        return set()
    try:
        data = json.loads(PROCESSED_PATH.read_text())
        return set(data.get("messageIds", []))
    except Exception:
        return set()


def save_processed(ids: set):
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_PATH.write_text(json.dumps({"messageIds": sorted(ids)}, indent=2))


def ensure_headers(sheets, spreadsheet_id: str):
    sheets.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range="Sheet1!A1:M1",
        valueInputOption="RAW",
        body={"values": DEFAULT_HEADERS},
    ).execute()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spreadsheet", required=True, help="Spreadsheet ID")
    ap.add_argument(
        "--query",
        default="to:clawsystss@gmail.com (complaint OR refund OR cancel OR cancellation OR angry OR upset)",
        help="Gmail search query",
    )
    ap.add_argument("--max", type=int, default=25)
    ap.add_argument("--no-headers", action="store_true")
    args = ap.parse_args()

    creds = load_creds()
    gmail = build("gmail", "v1", credentials=creds, cache_discovery=False)
    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)

    if not args.no_headers:
        ensure_headers(sheets, args.spreadsheet)

    processed = load_processed()

    # also avoid dupes by reading existing sheet message ids (col K)
    existing = set()
    try:
        resp = sheets.spreadsheets().values().get(
            spreadsheetId=args.spreadsheet, range="Sheet1!K2:K"
        ).execute()
        for row in resp.get("values", []) or []:
            if row:
                existing.add(row[0])
    except Exception:
        pass

    res = (
        gmail.users()
        .messages()
        .list(userId="me", q=args.query, maxResults=args.max)
        .execute()
    )
    msgs = res.get("messages", []) or []

    rows = []
    new_ids = []
    for m in msgs:
        mid = m["id"]
        if mid in processed or mid in existing:
            continue

        full = (
            gmail.users().messages().get(userId="me", id=mid, format="full").execute()
        )
        payload = full.get("payload", {})
        headers = payload.get("headers", [])
        subject = hdr(headers, "Subject")
        frm = hdr(headers, "From")

        internal_ms = int(full.get("internalDate", "0"))
        received = (
            dt.datetime.fromtimestamp(internal_ms / 1000, tz=dt.timezone.utc)
            .astimezone()
            .isoformat(timespec="minutes")
        )

        thread_id = full.get("threadId", "")
        body = extract_text(payload)
        summary = naive_summary(body)

        rows.append(
            [
                received,
                frm,
                subject,
                "",
                "",
                "",
                "",
                summary,
                "",
                "new",
                mid,
                thread_id,
                f"https://mail.google.com/mail/u/0/#inbox/{mid}",
            ]
        )
        new_ids.append(mid)

    if rows:
        sheets.spreadsheets().values().append(
            spreadsheetId=args.spreadsheet,
            range="Sheet1!A2",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": rows},
        ).execute()

    processed.update(new_ids)
    save_processed(processed)

    print(json.dumps({"found": len(msgs), "appended": len(rows)}, indent=2))


if __name__ == "__main__":
    main()
