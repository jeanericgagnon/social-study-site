#!/usr/bin/env python3
import csv
import json
import os
from datetime import datetime, timedelta, UTC
from pathlib import Path

import requests

WORKSPACE = Path('/Users/ericsysclaw/.openclaw/workspace')
OUTDIR = WORKSPACE / 'exports' / 'meta-ads'
CONF = OUTDIR / 'config.json'
GRAPH_VERSION = 'v21.0'

BASE_FIELDS = [
    'date_start', 'date_stop',
    'account_id', 'account_name',
    'campaign_id', 'campaign_name',
    'adset_id', 'adset_name',
    'ad_id', 'ad_name',
    'spend', 'impressions', 'reach', 'clicks', 'ctr', 'cpc', 'cpm',
    'actions', 'cost_per_action_type',
]

# Extra KPI slices using the same ads API/token.
BREAKDOWN_VARIANTS = [
    {'name': 'placement', 'breakdowns': ['publisher_platform', 'platform_position']},
    {'name': 'age_gender', 'breakdowns': ['age', 'gender']},
    {'name': 'device', 'breakdowns': ['device_platform']},
    {'name': 'region', 'breakdowns': ['region']},
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
        if k:
            out[k] = _num(item.get('value'))
    return out


def extract_follow_count(row: dict) -> float:
    amap = action_map(row, 'actions')
    return sum(v for k, v in amap.items() if k in FOLLOW_ACTION_TYPES)


def extract_follow_cpf(row: dict):
    cmap = action_map(row, 'cost_per_action_type')
    vals = [v for k, v in cmap.items() if k in FOLLOW_ACTION_TYPES]
    return min(vals) if vals else None


def pull_insights(token: str, ad_account_id: str, since: str, until: str, breakdowns=None):
    url = f'https://graph.facebook.com/{GRAPH_VERSION}/{ad_account_id}/insights'
    params = {
        'access_token': token,
        'fields': ','.join(BASE_FIELDS),
        'level': 'ad',
        'time_increment': '1',
        'time_range': json.dumps({'since': since, 'until': until}),
        'limit': 500,
    }
    if breakdowns:
        params['breakdowns'] = ','.join(breakdowns)

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
    action_types = set()
    cost_action_types = set()
    extra_dims = set()

    base_cols = {
        'date_start', 'date_stop',
        'account_id', 'account_name',
        'campaign_id', 'campaign_name',
        'adset_id', 'adset_name',
        'ad_id', 'ad_name',
        'spend', 'impressions', 'reach', 'clicks', 'ctr', 'cpc', 'cpm',
        'actions', 'cost_per_action_type',
    }

    for row in rows:
        action_types.update(action_map(row, 'actions').keys())
        cost_action_types.update(action_map(row, 'cost_per_action_type').keys())
        for k in row.keys():
            if k not in base_cols:
                extra_dims.add(k)

    action_cols = [f'action__{k}' for k in sorted(action_types)]
    cost_cols = [f'cost_per_action__{k}' for k in sorted(cost_action_types)]
    dim_cols = sorted(extra_dims)

    base_csv_cols = [
        'date_start', 'date_stop',
        'account_id', 'account_name',
        'campaign_id', 'campaign_name',
        'adset_id', 'adset_name',
        'ad_id', 'ad_name',
        'spend', 'impressions', 'reach', 'clicks', 'ctr', 'cpc', 'cpm',
        'follows', 'cost_per_follow',
        'actions_raw', 'cost_per_action_type_raw',
    ] + dim_cols

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


def save_dataset(rows, since, until, prefix='insights'):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')

    raw_path = OUTDIR / f'{prefix}_{since}_{until}_{ts}.json'
    csv_path = OUTDIR / f'{prefix}_{since}_{until}_{ts}.csv'
    latest_json = OUTDIR / f'{prefix}_latest.json'
    latest_csv = OUTDIR / f'{prefix}_latest.csv'

    raw_path.write_text(json.dumps(rows, indent=2))
    latest_json.write_text(json.dumps(rows, indent=2))

    cols, rows_out = normalize_rows(rows)
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows_out)
    latest_csv.write_text(csv_path.read_text())

    return {'rows': len(rows), 'columns': cols, 'latest_csv': str(latest_csv), 'latest_json': str(latest_json)}


def build_diagnostics(base_rows):
    by_date = {}
    for r in base_rows:
        d = r.get('date_start')
        if not d:
            continue
        x = by_date.setdefault(d, {'spend': 0.0, 'impressions': 0.0, 'clicks': 0.0, 'follows': 0.0})
        x['spend'] += _num(r.get('spend'))
        x['impressions'] += _num(r.get('impressions'))
        x['clicks'] += _num(r.get('clicks'))
        x['follows'] += extract_follow_count(r)

    dates = sorted(by_date.keys())
    if len(dates) < 2:
        return {'status': 'insufficient_history', 'dates': dates}

    latest = by_date[dates[-1]]
    prev = by_date[dates[-2]]

    def pct(new, old):
        return None if old == 0 else round((new - old) / old * 100, 2)

    return {
        'latest_date': dates[-1],
        'prev_date': dates[-2],
        'latest': latest,
        'prev': prev,
        'delta_pct': {
            'spend': pct(latest['spend'], prev['spend']),
            'impressions': pct(latest['impressions'], prev['impressions']),
            'clicks': pct(latest['clicks'], prev['clicks']),
            'follows': pct(latest['follows'], prev['follows']),
        }
    }


def main():
    cfg = load_config()
    token = (cfg.get('access_token') or '').strip()
    ad_account_id = (cfg.get('ad_account_id') or '').strip()
    if not token or not ad_account_id:
        raise SystemExit('Missing config: access_token/ad_account_id')

    today = datetime.now(UTC).date()
    since = (today - timedelta(days=30)).isoformat()
    until = today.isoformat()

    # Base pull
    base_rows = pull_insights(token, ad_account_id, since, until)
    base_saved = save_dataset(base_rows, since, until, 'insights')

    # Variant pulls for additional KPI slices.
    variants = {}
    for v in BREAKDOWN_VARIANTS:
        name = v['name']
        try:
            rows = pull_insights(token, ad_account_id, since, until, breakdowns=v['breakdowns'])
            saved = save_dataset(rows, since, until, f'insights_{name}')
            variants[name] = {'status': 'ok', 'breakdowns': v['breakdowns'], **saved}
        except Exception as e:
            variants[name] = {'status': 'error', 'breakdowns': v['breakdowns'], 'error': str(e)}

    total_spend = sum(_num(r.get('spend')) for r in base_rows)
    total_clicks = sum(int(_num(r.get('clicks'))) for r in base_rows)
    total_impr = sum(int(_num(r.get('impressions'))) for r in base_rows)
    total_follows = sum(extract_follow_count(r) for r in base_rows)
    blended_cpf = (total_spend / total_follows) if total_follows > 0 else None

    kpi_catalog = {
        'fixed_columns': base_saved['columns'],
        'dynamic_action_columns': [c for c in base_saved['columns'] if c.startswith('action__')],
        'dynamic_cost_per_action_columns': [c for c in base_saved['columns'] if c.startswith('cost_per_action__')],
        'variant_files': variants,
    }
    (OUTDIR / 'kpi_catalog_latest.json').write_text(json.dumps(kpi_catalog, indent=2))

    diagnostics = build_diagnostics(base_rows)
    (OUTDIR / 'diagnostics_latest.json').write_text(json.dumps(diagnostics, indent=2))

    summary = {
        'since': since,
        'until': until,
        'rows': len(base_rows),
        'total_spend': round(total_spend, 2),
        'total_clicks': total_clicks,
        'total_impressions': total_impr,
        'total_follows': int(total_follows) if float(total_follows).is_integer() else round(total_follows, 2),
        'blended_cost_per_follow': None if blended_cpf is None else round(blended_cpf, 6),
        'pulled_at': datetime.now(UTC).isoformat().replace('+00:00', 'Z'),
        'latest_csv': base_saved['latest_csv'],
        'latest_json': base_saved['latest_json'],
        'kpi_catalog': str(OUTDIR / 'kpi_catalog_latest.json'),
        'diagnostics': str(OUTDIR / 'diagnostics_latest.json'),
        'variant_status': {k: v['status'] for k, v in variants.items()},
    }
    (OUTDIR / 'summary_latest.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
