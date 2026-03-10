#!/usr/bin/env python3
import csv
import json
from datetime import datetime
from pathlib import Path

WORKSPACE = Path('/Users/ericsysclaw/.openclaw/workspace')
META_DIR = WORKSPACE / 'exports' / 'meta-ads'
ADS_CSV = META_DIR / 'insights_latest.csv'
FOLLOWERS_CSV = META_DIR / 'followers_daily.csv'
OUT_CSV = META_DIR / 'follow_kpis_latest.csv'
OUT_JSON = META_DIR / 'follow_kpis_summary_latest.json'


def read_ads_spend_by_date(path: Path):
    spend = {}
    if not path.exists():
        return spend
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d = row.get('date_start')
            if not d:
                continue
            spend[d] = spend.get(d, 0.0) + float(row.get('spend') or 0.0)
    return spend


def ensure_followers_template(path: Path):
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['date', 'followers_total'])


def read_followers_series(path: Path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d = row.get('date')
            total = row.get('followers_total')
            if not d or total in (None, ''):
                continue
            rows.append((d, float(total)))
    rows.sort(key=lambda x: x[0])
    return rows


def main():
    ensure_followers_template(FOLLOWERS_CSV)

    spend_by_date = read_ads_spend_by_date(ADS_CSV)
    followers = read_followers_series(FOLLOWERS_CSV)

    if len(followers) < 2:
        summary = {
            'status': 'waiting_for_followers_data',
            'message': 'Add at least 2 rows to followers_daily.csv to compute net-new followers and blended CPF.',
            'followers_csv': str(FOLLOWERS_CSV),
            'ads_csv': str(ADS_CSV),
            'generated_at': datetime.utcnow().isoformat() + 'Z',
        }
        OUT_JSON.write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        return

    out_rows = []
    total_spend = 0.0
    total_net_new = 0.0

    for i in range(1, len(followers)):
        prev_date, prev_total = followers[i - 1]
        date, total = followers[i]
        net_new = total - prev_total
        spend = spend_by_date.get(date, 0.0)
        cpf_blended = (spend / net_new) if net_new > 0 else None

        out_rows.append({
            'date': date,
            'followers_total': round(total, 2),
            'net_new_followers': round(net_new, 2),
            'ad_spend': round(spend, 2),
            'blended_cost_per_follow': '' if cpf_blended is None else round(cpf_blended, 4),
            'window_prev_date': prev_date,
        })

        total_spend += spend
        total_net_new += net_new

    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        cols = ['date', 'followers_total', 'net_new_followers', 'ad_spend', 'blended_cost_per_follow', 'window_prev_date']
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    total_cpf = (total_spend / total_net_new) if total_net_new > 0 else None
    summary = {
        'status': 'ok',
        'rows': len(out_rows),
        'total_spend': round(total_spend, 2),
        'total_net_new_followers': round(total_net_new, 2),
        'blended_cost_per_follow_total': None if total_cpf is None else round(total_cpf, 4),
        'output_csv': str(OUT_CSV),
        'followers_csv': str(FOLLOWERS_CSV),
        'generated_at': datetime.utcnow().isoformat() + 'Z',
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
