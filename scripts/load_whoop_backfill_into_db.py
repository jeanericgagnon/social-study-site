#!/usr/bin/env python3
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path('/Users/ericsysclaw/.openclaw/workspace')
DB_PATH = ROOT / 'knowledge' / 'advisory' / 'db' / 'health_advisory.db'
IN_PATH = ROOT / 'knowledge' / 'advisory' / 'data' / 'whoop' / 'backfill' / 'whoop_90d.json'


def dt(s):
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None


def pick_by_cycle_id(records, key='cycle_id'):
    m = {}
    for r in records or []:
        cid = r.get(key)
        if cid is not None:
            m[cid] = r
    return m


def main():
    j = json.loads(IN_PATH.read_text())
    recoveries = pick_by_cycle_id(j.get('recovery') or [], 'cycle_id')
    sleeps = pick_by_cycle_id(j.get('sleep') or [], 'cycle_id')
    cycles = {c.get('id'): c for c in (j.get('cycle') or []) if c.get('id') is not None}
    body = j.get('body') or {}
    profile = j.get('profile') or {}

    conn = sqlite3.connect(DB_PATH)
    try:
        n = 0
        for cid, cyc in cycles.items():
            start = dt(cyc.get('start') or cyc.get('created_at') or '')
            if not start:
                continue
            day = start.astimezone().date().isoformat()
            rec = recoveries.get(cid, {})
            sl = sleeps.get(cid, {})
            rec_score = (rec.get('score') or {})
            sl_score = (sl.get('score') or {})
            cy_score = (cyc.get('score') or {})

            raw = {'cycle': cyc, 'recovery': rec, 'sleep': sl, 'source': 'whoop_90d_backfill'}
            conn.execute(
                """
                INSERT INTO whoop_daily (
                  day, pulled_at_utc, user_id, recovery_score, hrv_rmssd, resting_hr,
                  sleep_performance, sleep_efficiency, sleep_consistency,
                  strain, weight_kg, raw_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(day) DO UPDATE SET
                  pulled_at_utc=excluded.pulled_at_utc,
                  user_id=excluded.user_id,
                  recovery_score=excluded.recovery_score,
                  hrv_rmssd=excluded.hrv_rmssd,
                  resting_hr=excluded.resting_hr,
                  sleep_performance=excluded.sleep_performance,
                  sleep_efficiency=excluded.sleep_efficiency,
                  sleep_consistency=excluded.sleep_consistency,
                  strain=excluded.strain,
                  weight_kg=excluded.weight_kg,
                  raw_json=excluded.raw_json,
                  updated_at=datetime('now')
                """,
                (
                    day,
                    j.get('pulled_at'),
                    profile.get('user_id'),
                    rec_score.get('recovery_score'),
                    rec_score.get('hrv_rmssd_milli'),
                    rec_score.get('resting_heart_rate'),
                    sl_score.get('sleep_performance_percentage'),
                    sl_score.get('sleep_efficiency_percentage'),
                    sl_score.get('sleep_consistency_percentage'),
                    cy_score.get('strain'),
                    body.get('weight_kilogram'),
                    json.dumps(raw),
                ),
            )
            n += 1
        conn.commit()
        print(f'upserted_days {n}')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
