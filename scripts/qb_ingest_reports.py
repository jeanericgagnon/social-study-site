#!/usr/bin/env python3
import base64
import json
import os
import re
from datetime import datetime
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

WORKSPACE = Path('/Users/ericsysclaw/.openclaw/workspace')
OUTDIR = WORKSPACE / 'exports' / 'qb-mail'
RAWDIR = OUTDIR / 'raw'
INDEX = OUTDIR / 'index.json'
METRICS = OUTDIR / 'finance-metrics.json'
LEDGER_TEXT = OUTDIR / 'finance-ledger-latest.txt'
TOKEN_PATH = WORKSPACE / 'gcal' / 'token_sys_send.json'


def load_creds(path: Path) -> Credentials:
    info = json.loads(path.read_text())
    creds = Credentials.from_authorized_user_info(info)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds


def decode_part(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + '==')


def extract_pdf_text(pdf_path: Path) -> str:
    if PdfReader is None:
        return ''
    try:
        reader = PdfReader(str(pdf_path))
        return '\n'.join((p.extract_text() or '') for p in reader.pages)
    except Exception:
        return ''


def parse_metrics(text: str) -> dict:
    def grab(label: str):
        m = re.search(rf"{re.escape(label)}\s+\$?(-?[\d,]+\.\d{{2}})", text)
        return float(m.group(1).replace(',', '')) if m else None

    return {
        'income_total': grab('Total Income'),
        'expenses_total': grab('Total Expenses'),
        'net_income': grab('NET INCOME'),
        'parsed_at': datetime.utcnow().isoformat() + 'Z',
    }


def run():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    RAWDIR.mkdir(parents=True, exist_ok=True)

    creds = load_creds(TOKEN_PATH)
    gmail = build('gmail', 'v1', credentials=creds, cache_discovery=False)

    query = 'from:quickbooks@notification.intuit.com newer_than:30d'
    res = gmail.users().messages().list(userId='me', q=query, maxResults=20).execute()
    messages = res.get('messages', [])

    index = {'messages': [], 'updated_at': datetime.utcnow().isoformat() + 'Z'}
    latest_fs_text = ''

    for m in messages:
        mid = m['id']
        full = gmail.users().messages().get(userId='me', id=mid, format='full').execute()
        headers = {h['name']: h['value'] for h in full.get('payload', {}).get('headers', [])}
        subject = headers.get('Subject', '')
        date = headers.get('Date', '')

        entry = {'id': mid, 'subject': subject, 'date': date, 'files': []}

        parts = full.get('payload', {}).get('parts', []) or []
        for p in parts:
            fn = p.get('filename') or ''
            if not fn:
                continue
            body = p.get('body', {})
            data = body.get('data')
            if not data and body.get('attachmentId'):
                att = gmail.users().messages().attachments().get(
                    userId='me', messageId=mid, id=body['attachmentId']
                ).execute()
                data = att.get('data')
            if not data:
                continue

            b = decode_part(data)
            safe_fn = f"{mid}_{fn}"
            out = RAWDIR / safe_fn
            out.write_bytes(b)
            entry['files'].append(str(out))

            if fn.lower().endswith('.pdf') and 'financial' in subject.lower():
                text = extract_pdf_text(out)
                if text:
                    txt_path = RAWDIR / f"{mid}_financial_statements.txt"
                    txt_path.write_text(text)
                    latest_fs_text = text

        index['messages'].append(entry)

    INDEX.write_text(json.dumps(index, indent=2))

    if latest_fs_text:
        LEDGER_TEXT.write_text(latest_fs_text)
        METRICS.write_text(json.dumps(parse_metrics(latest_fs_text), indent=2))

    print(f"Indexed {len(index['messages'])} QuickBooks emails")
    if latest_fs_text:
        print(f"Updated {LEDGER_TEXT}")
        print(f"Updated {METRICS}")


if __name__ == '__main__':
    run()
