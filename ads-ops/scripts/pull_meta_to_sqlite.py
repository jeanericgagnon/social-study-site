#!/usr/bin/env python3
import os, json, sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone
import requests

DB_PATH = os.getenv("KPI_DB_PATH", "ads-ops/db/kpi.sqlite")
API_VERSION = os.getenv("META_API_VERSION", "v25.0")
BASE = f"https://graph.facebook.com/{API_VERSION}"


def _load_meta_config_fallback():
    cfg_path = Path("exports/meta-ads/config.json")
    if not cfg_path.exists():
        return {}, False
    try:
        cfg = json.loads(cfg_path.read_text())
        return cfg, True
    except Exception:
        return {}, True


cfg, has_cfg = _load_meta_config_fallback()
TOKEN = (os.getenv("META_ACCESS_TOKEN") or cfg.get("access_token") or "").strip()
AD_ACCOUNT = (os.getenv("META_AD_ACCOUNT_ID") or cfg.get("ad_account_id") or "").strip()
if not TOKEN or not AD_ACCOUNT:
    src = "(checked env + exports/meta-ads/config.json)" if has_cfg else "(checked env; no exports/meta-ads/config.json found)"
    raise SystemExit(f"Missing META_ACCESS_TOKEN or META_AD_ACCOUNT_ID {src}")
if not AD_ACCOUNT.startswith("act_"):
    AD_ACCOUNT = f"act_{AD_ACCOUNT}"

FIELDS = [
  "account_id","account_name","campaign_id","campaign_name","adset_id","adset_name","ad_id","ad_name",
  "date_start","date_stop","spend","impressions","reach","frequency","cpm","cpp",
  "clicks","ctr","unique_ctr","cpc","inline_link_clicks","outbound_clicks","website_ctr",
  "actions","action_values","cost_per_action_type",
  "conversions","conversion_values","cost_per_conversion",
  "purchase_roas","website_purchase_roas",
  "video_play_actions","video_p25_watched_actions","video_p50_watched_actions",
  "video_p75_watched_actions","video_p95_watched_actions","video_p100_watched_actions",
  "video_avg_time_watched_actions","video_thruplay_watched_actions",
]

BREAKDOWN_VARIANTS = {
    "placement": ["publisher_platform", "platform_position"],
    "age_gender": ["age", "gender"],
    "device": ["device_platform"],
    "region": ["region"],
    "city": ["city"],
}


def fetch(level: str, since: str, until: str, breakdowns=None):
    params = {
        "access_token": TOKEN,
        "level": level,
        "time_range": json.dumps({"since": since, "until": until}),
        "time_increment": 1,
        "fields": ",".join(FIELDS),
        "limit": 500,
    }
    if breakdowns:
        params["breakdowns"] = ",".join(breakdowns)

    url = f"{BASE}/{AD_ACCOUNT}/insights"
    all_rows = []
    while True:
        r = requests.get(url, params=params, timeout=90)
        r.raise_for_status()
        body = r.json()
        all_rows.extend(body.get("data", []))
        nxt = body.get("paging", {}).get("next")
        if not nxt:
            break
        url, params = nxt, {}
    return all_rows


def ensure_tables(conn):
    conn.execute("""
      CREATE TABLE IF NOT EXISTS kpi_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pulled_at_utc TEXT NOT NULL,
        source TEXT NOT NULL,
        ad_account_id TEXT NOT NULL,
        date_start TEXT NOT NULL,
        date_stop TEXT NOT NULL,
        level TEXT NOT NULL,
        payload_json TEXT NOT NULL
      )
    """)
    conn.execute("""
      CREATE TABLE IF NOT EXISTS kpi_breakdown_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pulled_at_utc TEXT NOT NULL,
        source TEXT NOT NULL,
        ad_account_id TEXT NOT NULL,
        date_start TEXT NOT NULL,
        date_stop TEXT NOT NULL,
        level TEXT NOT NULL,
        variant TEXT NOT NULL,
        breakdowns_json TEXT NOT NULL,
        payload_json TEXT NOT NULL
      )
    """)


def main():
    conn = sqlite3.connect(DB_PATH)
    ensure_tables(conn)

    now = datetime.now(timezone.utc).isoformat()
    lookback_days = int(os.getenv("META_LOOKBACK_DAYS", "30"))
    today = datetime.now(timezone.utc).date()
    since = (today - timedelta(days=lookback_days)).isoformat()
    until = today.isoformat()

    levels = [x.strip() for x in os.getenv("META_PULL_LEVELS", "campaign,adset,ad").split(",") if x.strip()]

    for level in levels:
        try:
            rows = fetch(level, since, until)
            conn.execute(
              "INSERT INTO kpi_snapshots (pulled_at_utc, source, ad_account_id, date_start, date_stop, level, payload_json) VALUES (?,?,?,?,?,?,?)",
              (now, "meta_marketing_api", AD_ACCOUNT, since, until, level, json.dumps(rows))
            )
            print(f"saved {level}: {len(rows)} rows")
        except Exception as e:
            print(f"warn {level}: {e}")

    for level in ["ad"]:
        for variant, breakdowns in BREAKDOWN_VARIANTS.items():
            try:
                rows = fetch(level, since, until, breakdowns=breakdowns)
                conn.execute(
                  "INSERT INTO kpi_breakdown_snapshots (pulled_at_utc, source, ad_account_id, date_start, date_stop, level, variant, breakdowns_json, payload_json) VALUES (?,?,?,?,?,?,?,?,?)",
                  (now, "meta_marketing_api", AD_ACCOUNT, since, until, level, variant, json.dumps(breakdowns), json.dumps(rows))
                )
                print(f"saved {level}:{variant}: {len(rows)} rows")
            except Exception as e:
                print(f"warn {level}:{variant}: {e}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
