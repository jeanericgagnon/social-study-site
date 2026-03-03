#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
ROOT = Path('/Users/ericsysclaw/.openclaw/workspace')
GCAL = ROOT / 'gcal'
TOKEN_CANDIDATES = [
    GCAL / 'token_eric_readonly.json',
    GCAL / 'token_gmail_clawsystss.json',
    GCAL / 'token_all.json',
    GCAL / 'token.json',
]


def load_creds():
    token_path = next((p for p in TOKEN_CANDIDATES if p.exists()), None)
    if not token_path:
        raise SystemExit('No Gmail token file found in gcal/.')
    data = json.loads(token_path.read_text())
    creds = Credentials(
        token=data.get('token'),
        refresh_token=data.get('refresh_token'),
        token_uri=data.get('token_uri'),
        client_id=data.get('client_id'),
        client_secret=data.get('client_secret'),
        scopes=data.get('scopes') or SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data['token'] = creds.token
        token_path.write_text(json.dumps(data, indent=2))
    return creds


def header_map(payload):
    out = {}
    for h in payload.get('headers', []):
        out[h.get('name', '').lower()] = h.get('value')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--query', default='from:eric@thesocial.study')
    ap.add_argument('--max', type=int, default=300)
    ap.add_argument('--outdir', default=str(ROOT / 'discord-tss-second-brain' / 'knowledge' / 'emails' / 'raw'))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    outfile = outdir / f'email-digest-{stamp}.jsonl'

    creds = load_creds()
    svc = build('gmail', 'v1', credentials=creds, cache_discovery=False)

    written = 0
    page_token = None
    with outfile.open('w') as f:
        while written < args.max:
            resp = svc.users().messages().list(
                userId='me',
                q=args.query,
                maxResults=min(100, args.max - written),
                pageToken=page_token,
            ).execute()
            msgs = resp.get('messages', [])
            if not msgs:
                break

            for m in msgs:
                full = svc.users().messages().get(
                    userId='me', id=m['id'], format='metadata', metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()
                h = header_map(full.get('payload', {}))
                row = {
                    'id': full.get('id'),
                    'threadId': full.get('threadId'),
                    'internalDate': full.get('internalDate'),
                    'from': h.get('from'),
                    'to': h.get('to'),
                    'subject': h.get('subject'),
                    'date': h.get('date'),
                    'snippet': full.get('snippet'),
                    'labelIds': full.get('labelIds', []),
                }
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                written += 1
                if written >= args.max:
                    break

            page_token = resp.get('nextPageToken')
            if not page_token:
                break

    print(json.dumps({'outfile': str(outfile), 'count': written, 'query': args.query}, indent=2))


if __name__ == '__main__':
    main()
