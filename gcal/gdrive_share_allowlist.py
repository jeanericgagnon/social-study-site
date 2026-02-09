#!/usr/bin/env python3
"""Share Google Drive files/folders with a strict allowlist.

This is a safety guardrail: it will ONLY grant permissions to allowlisted emails.

Allowlist:
- eric@thesocial.study
- nick@thesocial.study

Uses Sys token (token_sys.json) if present.

Examples:
  python gdrive_share_allowlist.py --file <FILE_ID_OR_URL> --email eric@thesocial.study --role writer
  python gdrive_share_allowlist.py --file <FOLDER_ID_OR_URL> --email nick@thesocial.study --role reader

Roles:
- reader (view)
- writer (edit)

Notes:
- This script only ADDS/UPDATES a permission for a specific email.
- It does not remove other existing permissions (we can add a "lockdown" command later).
"""

import argparse
import json
import re
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

ALLOWLIST = {
    "eric@thesocial.study",
    "nick@thesocial.study",
    "quino@thesocial.study",
}

HERE = Path(__file__).resolve().parent
TOKEN_PATH = HERE / (
    "token_sys.json"
    if (HERE / "token_sys.json").exists()
    else ("token_all.json" if (HERE / "token_all.json").exists() else "token.json")
)


def parse_file_id(s: str) -> str:
    # Accept raw id or common Drive URLs.
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", s)  # docs/sheets style
    if m:
        return m.group(1)
    m = re.search(r"folders/([a-zA-Z0-9_-]+)", s)
    if m:
        return m.group(1)
    m = re.search(r"id=([a-zA-Z0-9_-]+)", s)
    if m:
        return m.group(1)
    return s


def load_creds():
    if not TOKEN_PATH.exists():
        raise SystemExit(f"Missing token at {TOKEN_PATH}. Run google_auth_sys_drive_calendar.py first.")
    data = json.loads(TOKEN_PATH.read_text())
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes"),
    )
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        TOKEN_PATH.write_text(json.dumps(data, indent=2))
    return creds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="File/folder id or URL")
    ap.add_argument("--email", required=True)
    ap.add_argument("--role", choices=["reader", "writer"], default="reader")
    args = ap.parse_args()

    email = args.email.strip().lower()
    if email not in ALLOWLIST:
        raise SystemExit(
            f"Refusing to share: {email} is not allowlisted. Allowed: {', '.join(sorted(ALLOWLIST))}"
        )

    file_id = parse_file_id(args.file)

    creds = load_creds()
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    perm = {"type": "user", "role": args.role, "emailAddress": email}

    created = (
        svc.permissions()
        .create(
            fileId=file_id,
            body=perm,
            sendNotificationEmail=False,
            fields="id",
        )
        .execute()
    )

    print(json.dumps({"fileId": file_id, "permissionId": created.get("id"), "email": email, "role": args.role}, indent=2))


if __name__ == "__main__":
    main()
