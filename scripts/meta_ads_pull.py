#!/usr/bin/env python3
import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

WORKSPACE = Path('/Users/ericsysclaw/.openclaw/workspace')
OUTDIR = WORKSPACE / 'exports' / 'meta-ads'
CONF = WORKSPACE / 'exports' / 'meta-ads' / 'config.json'


def load_config():
    if CONF.exists():
        return json.loads(CONF.read_text())
    token = os.getenv('META_ACCESS_TOKEN', '').strip()
    act = os.getenv('META_AD_ACCOUNT_ID', '').strip()
    return {'access_token': token, 'ad_account_id': act}


def pull_insights(token: str, ad_account_id: str, since: str, until: str):
    url = f'https://graph.facebook.com/v21.0/{ad_account_id}/insights'
    params = {
        'access_token': token,
        'fields': 'date_start,date_stop,account_name,campaign_name,adset_name,ad_name,spend,impressions,reach,clicks,ctr,cpc,cpm',
        'level': 'ad',
        'time_increment': '1',
        'time_range': json.dumps({'since': since, 'until': until}),
        'limit': 500,
    }
    all_rows = []
    while True:
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        j = r.json()
        all_rows.extend(j.get('data', []))
        paging = j.get('paging', {})
        nxt = paging.get('next')
        if not nxt:
            break
        url = nxt
        params = None
    return all_rows


def save(rows, since: str, until: str):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    raw_path = OUTDIR / f'insights_{since}_{until}_{ts}.json'
    csv_path = OUTDIR / f'insights_{since}_{until}_{ts}.csv'
    latest_csv = OUTDIR / 'insights_latest.csv'
    latest_json = OUTDIR / 'insights_latest.json'

    raw_path.write_text(json.dumps(rows, indent=2))
    latest_json.write_text(json.dumps(rows, indent=2))

    cols = ['date_start','date_stop','account_name','campaign_name','adset_name','ad_name','spend','impressions','reach','clicks','ctr','cpc','cpm']
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in cols})
    latest_csv.write_text(csv_path.read_text())

    total_spend = sum(float(r.get('spend', 0) or 0) for r in rows)
    total_clicks = sum(int(float(r.get('clicks', 0) or 0)) for r in rows)
    total_impr = sum(int(float(r.get('impressions', 0) or 0)) for r in rows)

    summary = {
        'since': since,
        'until': until,
        'rows': len(rows),
        'total_spend': round(total_spend, 2),
        'total_clicks': total_clicks,
        'total_impressions': total_impr,
        'pulled_at': datetime.utcnow().isoformat() + 'Z',
        'latest_csv': str(latest_csv),
    }
    (OUTDIR / 'summary_latest.json').write_text(json.dumps(summary, indent=2))
    return summary


def main():
    cfg = load_config()
    token = (cfg.get('access_token') or '').strip()
    act = (cfg.get('ad_account_id') or '').strip()
    if not token or not act:
        raise SystemExit('Missing config: access_token/ad_account_id')

    today = datetime.utcnow().date()
    since = (today - timedelta(days=30)).isoformat()
    until = today.isoformat()

    rows = pull_insights(token, act, since, until)
    summary = save(rows, since, until)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
