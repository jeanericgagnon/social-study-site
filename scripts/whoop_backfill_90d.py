#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, UTC
from pathlib import Path

TOK_PATH = Path('/Users/ericsysclaw/.openclaw/workspace/.secrets/whoop.tokens.json')
ENV_PATH = Path('/Users/ericsysclaw/.openclaw/workspace/.secrets/whoop.secret.env')
OUT_DIR = Path('/Users/ericsysclaw/.openclaw/workspace/knowledge/advisory/data/whoop/backfill')
TOKEN_URL = 'https://api.prod.whoop.com/oauth/oauth2/token'
BASE = 'https://api.prod.whoop.com/developer'


def load_env(path: Path):
    vals = {}
    if path.exists():
        for ln in path.read_text().splitlines():
            if '=' in ln:
                k, v = ln.split('=', 1)
                vals[k.strip()] = v.strip()
    return vals


def refresh_token(tok: dict, env: dict):
    payload = urllib.parse.urlencode({
        'grant_type': 'refresh_token',
        'refresh_token': tok.get('refresh_token', ''),
        'client_id': env.get('WHOOP_CLIENT_ID', ''),
        'client_secret': env.get('WHOOP_CLIENT_SECRET', ''),
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=payload, method='POST', headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        new_tok = json.loads(r.read().decode())
    if 'refresh_token' not in new_tok and tok.get('refresh_token'):
        new_tok['refresh_token'] = tok['refresh_token']
    TOK_PATH.write_text(json.dumps(new_tok, indent=2))
    TOK_PATH.chmod(0o600)
    return new_tok


def api_get(access_token: str, endpoint: str):
    req = urllib.request.Request(BASE + endpoint, headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def collect_collection(access_token: str, endpoint: str, start_iso: str, end_iso: str, limit: int = 25):
    records = []
    next_token = None
    while True:
        q = {'limit': str(limit), 'start': start_iso, 'end': end_iso}
        if next_token:
            q['nextToken'] = next_token
        ep = endpoint + '?' + urllib.parse.urlencode(q)
        page = api_get(access_token, ep)
        recs = page.get('records') or []
        records.extend(recs)
        next_token = page.get('next_token') or page.get('nextToken')
        if not next_token:
            break
    return records


def main():
    tok = json.loads(TOK_PATH.read_text())
    env = load_env(ENV_PATH)
    tok = refresh_token(tok, env)
    access = tok['access_token']

    end = datetime.now(UTC)
    start = end - timedelta(days=90)
    start_iso = start.replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    end_iso = end.replace(microsecond=0).isoformat().replace('+00:00', 'Z')

    payload = {
        'pulled_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
        'range': {'start': start_iso, 'end': end_iso, 'days': 90},
        'profile': api_get(access, '/v2/user/profile/basic'),
        'body': api_get(access, '/v2/user/measurement/body'),
        'recovery': collect_collection(access, '/v2/recovery', start_iso, end_iso),
        'sleep': collect_collection(access, '/v2/activity/sleep', start_iso, end_iso),
        'workout': collect_collection(access, '/v2/activity/workout', start_iso, end_iso),
        'cycle': collect_collection(access, '/v2/cycle', start_iso, end_iso),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / 'whoop_90d.json'
    out.write_text(json.dumps(payload, indent=2))
    print(str(out))
    print('recovery', len(payload['recovery']))
    print('sleep', len(payload['sleep']))
    print('workout', len(payload['workout']))
    print('cycle', len(payload['cycle']))


if __name__ == '__main__':
    main()
