#!/usr/bin/env python3
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

TOK_PATH = Path('/Users/ericsysclaw/.openclaw/workspace/.secrets/whoop.tokens.json')
ENV_PATH = Path('/Users/ericsysclaw/.openclaw/workspace/.secrets/whoop.secret.env')
OUT_DIR = Path('/Users/ericsysclaw/.openclaw/workspace/knowledge/advisory/data/whoop')
TOKEN_URL = 'https://api.prod.whoop.com/oauth/oauth2/token'
BASE = 'https://api.prod.whoop.com/developer'


def load_env(path: Path):
    vals = {}
    if not path.exists():
        return vals
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
    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        method='POST',
        headers={'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        new_tok = json.loads(r.read().decode())
    if 'refresh_token' not in new_tok and tok.get('refresh_token'):
        new_tok['refresh_token'] = tok['refresh_token']
    TOK_PATH.write_text(json.dumps(new_tok, indent=2))
    TOK_PATH.chmod(0o600)
    return new_tok


def api_get(access_token: str, endpoint: str):
    req = urllib.request.Request(
        BASE + endpoint,
        headers={'Authorization': f'Bearer {access_token}', 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    if not TOK_PATH.exists():
        raise SystemExit('Missing tokens file')
    tok = json.loads(TOK_PATH.read_text())
    env = load_env(ENV_PATH)

    tok = refresh_token(tok, env)
    access = tok['access_token']

    payload = {
        'pulled_at': datetime.utcnow().isoformat() + 'Z',
        'profile': api_get(access, '/v2/user/profile/basic'),
        'body': api_get(access, '/v2/user/measurement/body'),
        'recovery': api_get(access, '/v2/recovery?limit=1'),
        'sleep': api_get(access, '/v2/activity/sleep?limit=1'),
        'workout': api_get(access, '/v2/activity/workout?limit=5'),
        'cycle': api_get(access, '/v2/cycle?limit=1'),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    day = datetime.now().strftime('%Y-%m-%d')
    out = OUT_DIR / f'{day}.json'
    out.write_text(json.dumps(payload, indent=2))
    print(str(out))


if __name__ == '__main__':
    main()
