#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path

ROOT = Path('/Users/ericsysclaw/.openclaw/workspace')
DB_PATH = ROOT / 'knowledge' / 'advisory' / 'db' / 'health_advisory.db'
WHOOP_DIR = ROOT / 'knowledge' / 'advisory' / 'data' / 'whoop'


def first_record(obj):
    recs = (obj or {}).get('records') or []
    return recs[0] if recs else {}


def upsert_file(conn, p: Path):
    j = json.loads(p.read_text())
    day = p.stem
    recovery = first_record(j.get('recovery'))
    sleep = first_record(j.get('sleep'))
    cycle = first_record(j.get('cycle'))
    body = j.get('body') or {}
    profile = j.get('profile') or {}

    rec_score = (recovery.get('score') or {})
    sl_score = (sleep.get('score') or {})
    cy_score = (cycle.get('score') or {})

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
            json.dumps(j),
        ),
    )


def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        files = sorted(WHOOP_DIR.glob('*.json'))
        for p in files:
            upsert_file(conn, p)
        conn.commit()
        print(f'loaded {len(files)} files')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
