#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

WORKSPACE = Path('/Users/ericsysclaw/.openclaw/workspace')
CONF = WORKSPACE / 'exports' / 'meta-ads' / 'config.json'
OUT = WORKSPACE / 'exports' / 'meta-ads' / 'follower_demographics_city_latest.json'
HISTORY_DIR = WORKSPACE / 'exports' / 'meta-ads' / 'follower_demographics_city_history'


def main():
    cfg = json.loads(CONF.read_text())
    token = (cfg.get('access_token') or '').strip()
    if not token:
        raise SystemExit('Missing access_token in exports/meta-ads/config.json')

    pages = requests.get(
        'https://graph.facebook.com/v25.0/me/accounts',
        params={'access_token': token, 'fields': 'id,name,instagram_business_account'},
        timeout=60,
    )
    pages.raise_for_status()
    ig_id = None
    for p in pages.json().get('data', []):
        ig_id = (p.get('instagram_business_account') or {}).get('id')
        if ig_id:
            break
    if not ig_id:
        raise SystemExit('No instagram_business_account linked to accessible pages')

    r = requests.get(
        f'https://graph.facebook.com/v25.0/{ig_id}/insights',
        params={
            'metric': 'follower_demographics',
            'period': 'lifetime',
            'metric_type': 'total_value',
            'breakdown': 'city',
            'access_token': token,
        },
        timeout=90,
    )
    r.raise_for_status()
    js = r.json()

    results = (
        (js.get('data') or [{}])[0]
        .get('total_value', {})
        .get('breakdowns', [{}])[0]
        .get('results', [])
    )

    rows = []
    for x in results:
        vals = x.get('dimension_values') or []
        city = vals[0] if vals else 'Unknown'
        rows.append({'city': city, 'followers': int(x.get('value') or 0)})

    rows.sort(key=lambda x: x['followers'], reverse=True)

    updated_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    payload = {
        'updated_at': updated_at,
        'ig_user_id': ig_id,
        'metric': 'follower_demographics',
        'period': 'lifetime',
        'metric_type': 'total_value',
        'breakdown': 'city',
        'rows': rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2))

    ts = updated_at.replace(':', '').replace('-', '').replace('T', '_').replace('Z', 'Z')
    hist_file = HISTORY_DIR / f'follower_demographics_city_{ts}.json'
    hist_file.write_text(json.dumps(payload, indent=2))

    print(json.dumps({'ok': True, 'rows': len(rows), 'out': str(OUT), 'history': str(hist_file)}, indent=2))


if __name__ == '__main__':
    main()
