#!/usr/bin/env python3
import csv
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

WORKSPACE = Path('/Users/ericsysclaw/.openclaw/workspace')
OUTDIR = WORKSPACE / 'exports' / 'meta-ads'
CONF = OUTDIR / 'config.json'

GRAPH_VERSION = 'v21.0'

BASE_FIELDS = [
    # Keep this to fields verified on this account; dynamic KPI depth comes from actions/cost_per_action_type.
    'date_start', 'date_stop', 'account_name', 'campaign_name', 'adset_name', 'ad_name',
    'spend', 'impressions', 'reach', 'clicks', 'ctr', 'cpc', 'cpm',
    'actions', 'cost_per_action_type',
]

FOLLOW_ACTION_TYPES = {
    'follow', 'follows', 'instagram_profile_follow', 'ig_profile_follow', 'page_like', 'like'
}


def load_config():
    if CONF.exists():
        return json.loads(CONF.read_text())
    return {
        'access_token': os.getenv('META_ACCESS_TOKEN', '').strip(),
        'ad_account_id': os.getenv('META_AD_ACCOUNT_ID', '').strip(),
    }


def _num(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def _as_json(v):
    if isinstance(v, (list, dict)):
        return json.dumps(v, separators=(',', ':'), ensure_ascii=False)
    return v


def action_map(row: dict, key: str):
    out = {}
    for item in row.get(key, []) or []:
        k = str(item.get('action_type', '')).strip().lower()
        if not k:
            continue
        out[k] = _num(item.get('value'))
    return out


def extract_follow_count(row: dict) -> float:
    amap = action_map(row, 'actions')
    return sum(v for k, v in amap.items() if k in FOLLOW_ACTION_TYPES)


def extract_follow_cpf(row: dict):
    cmap = action_map(row, 'cost_per_action_type')
    vals = [v for k, v in cmap.items() if k in FOLLOW_ACTION_TYPES]
    return min(vals) if vals else None


def pull_insights(token: str, ad_account_id: str, since: str, until: str):
    url = f'https://graph.facebook.com/{GRAPH_VERSION}/{ad_account_id}/insights'
    params = {
        'access_token': token,
        'fields': ','.join(BASE_FIELDS),
        'level': 'ad',
        'time_increment': '1',
        'time_range': json.dumps({'since': since, 'until': until}),
        'limit': 500,
    }

    rows = []
    while True:
        r = requests.get(url, params=params, timeout=90)
        r.raise_for_status()
        payload = r.json()
        rows.extend(payload.get('data', []))
        nxt = (payload.get('paging') or {}).get('next')
        if not nxt:
            break
        url, params = nxt, None

    return rows


def normalize_rows(rows):
    # Discover dynamic action-type columns.
    action_types = set()
    cost_action_types = set()
    for row in rows:
        action_types.update(action_map(row, 'actions').keys())
        cost_action_types.update(action_map(row, 'cost_per_action_type').keys())

    action_cols = [f'action__{k}' for k in sorted(action_types)]
    cost_cols = [f'cost_per_action__{k}' for k in sorted(cost_action_types)]

    base_csv_cols = [
        'date_start', 'date_stop', 'account_name', 'campaign_name', 'adset_name', 'ad_name',
        'spend', 'impressions', 'reach', 'clicks', 'ctr', 'cpc', 'cpm',
        'follows', 'cost_per_follow',
        'actions_raw', 'cost_per_action_type_raw',
    ]

    cols = base_csv_cols + action_cols + cost_cols
    out_rows = []

    for row in rows:
        actions = action_map(row, 'actions')
        costs = action_map(row, 'cost_per_action_type')

        out = {k: row.get(k, '') for k in base_csv_cols if k not in {'follows', 'cost_per_follow', 'actions_raw', 'cost_per_action_type_raw'}}

        follows = extract_follow_count(row)
        cpf = extract_follow_cpf(row)
        out['follows'] = int(follows) if follows.is_integer() else round(follows, 4)
        out['cost_per_follow'] = '' if cpf is None else round(cpf, 6)

        out['actions_raw'] = _as_json(row.get('actions', []))
        out['cost_per_action_type_raw'] = _as_json(row.get('cost_per_action_type', []))

        for k in sorted(action_types):
            out[f'action__{k}'] = actions.get(k, '')
        for k in sorted(cost_action_types):
            out[f'cost_per_action__{k}'] = costs.get(k, '')

        out_rows.append(out)

    return cols, out_rows


def save(rows, since: str, until: str):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

    raw_path = OUTDIR / f'insights_{since}_{until}_{ts}.json'
    csv_path = OUTDIR / f'insights_{since}_{until}_{ts}.csv'
    latest_json = OUTDIR / 'insights_latest.json'
    latest_csv = OUTDIR / 'insights_latest.csv'

    raw_path.write_text(json.dumps(rows, indent=2))
    latest_json.write_text(json.dumps(rows, indent=2))

    cols, rows_out = normalize_rows(rows)

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for r in rows_out:
            writer.writerow(r)
    latest_csv.write_text(csv_path.read_text())

    total_spend = sum(_num(r.get('spend')) for r in rows)
    total_clicks = sum(int(_num(r.get('clicks'))) for r in rows)
    total_impr = sum(int(_num(r.get('impressions'))) for r in rows)
    total_follows = sum(extract_follow_count(r) for r in rows)
    blended_cpf = (total_spend / total_follows) if total_follows > 0 else None

    kpi_catalog = {
        'fixed_columns': cols,
        'dynamic_action_columns': [c for c in cols if c.startswith('action__')],
        'dynamic_cost_per_action_columns': [c for c in cols if c.startswith('cost_per_action__')],
    }
    (OUTDIR / 'kpi_catalog_latest.json').write_text(json.dumps(kpi_catalog, indent=2))

    summary = {
        'since': since,
        'until': until,
        'rows': len(rows),
        'total_spend': round(total_spend, 2),
        'total_clicks': total_clicks,
        'total_impressions': total_impr,
        'total_follows': int(total_follows) if float(total_follows).is_integer() else round(total_follows, 2),
        'blended_cost_per_follow': None if blended_cpf is None else round(blended_cpf, 6),
        'pulled_at': datetime.utcnow().isoformat() + 'Z',
        'latest_csv': str(latest_csv),
        'latest_json': str(latest_json),
        'kpi_catalog': str(OUTDIR / 'kpi_catalog_latest.json'),
    }
    (OUTDIR / 'summary_latest.json').write_text(json.dumps(summary, indent=2))
    return summary


def main():
    cfg = load_config()
    token = (cfg.get('access_token') or '').strip()
    ad_account_id = (cfg.get('ad_account_id') or '').strip()
    if not token or not ad_account_id:
        raise SystemExit('Missing config: access_token/ad_account_id')

    today = datetime.utcnow().date()
    since = (today - timedelta(days=30)).isoformat()
    until = today.isoformat()

    rows = pull_insights(token, ad_account_id, since, until)
    summary = save(rows, since, until)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
