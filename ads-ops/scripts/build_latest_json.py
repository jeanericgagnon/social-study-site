#!/usr/bin/env python3
import os, json, sqlite3
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = os.getenv("KPI_DB_PATH", "ads-ops/db/kpi.sqlite")
OUT = Path("ads-ops/dashboard/data/latest.json")
OUT.parent.mkdir(parents=True, exist_ok=True)


def fnum(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def aggregate_campaign(rows):
    by_campaign = {}
    for r in rows:
        cid = (r.get("campaign_id") or "").strip()
        if not cid:
            continue
        x = by_campaign.setdefault(cid, {
            "campaign_id": cid,
            "campaign_name": r.get("campaign_name") or "Unknown Campaign",
            "spend": 0.0,
            "impressions": 0.0,
            "clicks": 0.0,
            "ctr": 0.0,
            "cpc": None,
        })
        x["spend"] += fnum(r.get("spend"))
        x["impressions"] += fnum(r.get("impressions"))
        x["clicks"] += fnum(r.get("clicks"))

    out = []
    for x in by_campaign.values():
        x["ctr"] = (x["clicks"] / x["impressions"] * 100.0) if x["impressions"] > 0 else 0.0
        x["cpc"] = (x["spend"] / x["clicks"]) if x["clicks"] > 0 else None
        out.append(x)

    out.sort(key=lambda z: (z["cpc"] is None, z["cpc"] if z["cpc"] is not None else 999999))
    return out


def aggregate_ads(rows):
    by_ad = {}
    for r in rows:
        aid = (r.get("ad_id") or "").strip()
        if not aid:
            continue
        x = by_ad.setdefault(aid, {
            "ad_id": aid,
            "ad_name": r.get("ad_name") or "Unknown Ad",
            "campaign_id": r.get("campaign_id") or "",
            "campaign_name": r.get("campaign_name") or "Unknown Campaign",
            "adset_id": r.get("adset_id") or "",
            "adset_name": r.get("adset_name") or "",
            "spend": 0.0,
            "impressions": 0.0,
            "clicks": 0.0,
            "ctr": 0.0,
            "cpc": None,
        })
        x["spend"] += fnum(r.get("spend"))
        x["impressions"] += fnum(r.get("impressions"))
        x["clicks"] += fnum(r.get("clicks"))

    out = []
    for x in by_ad.values():
        x["ctr"] = (x["clicks"] / x["impressions"] * 100.0) if x["impressions"] > 0 else 0.0
        x["cpc"] = (x["spend"] / x["clicks"]) if x["clicks"] > 0 else None
        out.append(x)

    out.sort(key=lambda z: (z["cpc"] is None, z["cpc"] if z["cpc"] is not None else 999999))
    return out


conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

conn.execute("""CREATE TABLE IF NOT EXISTS kpi_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pulled_at_utc TEXT NOT NULL,
  source TEXT NOT NULL,
  ad_account_id TEXT NOT NULL,
  date_start TEXT NOT NULL,
  date_stop TEXT NOT NULL,
  level TEXT NOT NULL,
  payload_json TEXT NOT NULL
)""")
conn.execute("""CREATE TABLE IF NOT EXISTS follower_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pulled_at_utc TEXT NOT NULL,
  source TEXT NOT NULL,
  username TEXT NOT NULL,
  follower_count INTEGER NOT NULL,
  payload_json TEXT NOT NULL
)""")
conn.execute("""CREATE TABLE IF NOT EXISTS follower_city_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pulled_at_utc TEXT NOT NULL,
  source TEXT NOT NULL,
  ig_user_id TEXT,
  city TEXT NOT NULL,
  follower_count INTEGER NOT NULL
)""")

latest_by_level = conn.execute("""
SELECT s.*
FROM kpi_snapshots s
JOIN (
  SELECT level, MAX(id) AS max_id
  FROM kpi_snapshots
  WHERE source='meta_marketing_api'
  GROUP BY level
) t ON t.max_id = s.id
ORDER BY s.id DESC
""").fetchall()

latest_follow = conn.execute("""
SELECT * FROM follower_snapshots
ORDER BY pulled_at_utc DESC, id DESC
LIMIT 1
""").fetchone()

city_ts_rows = conn.execute("""
SELECT DISTINCT pulled_at_utc
FROM follower_city_snapshots
ORDER BY pulled_at_utc DESC
LIMIT 2
""").fetchall()

followers_city = []
followers_city_delta = []
if city_ts_rows:
    latest_ts = city_ts_rows[0][0]
    prev_ts = city_ts_rows[1][0] if len(city_ts_rows) > 1 else None

    latest_rows = conn.execute("""
    SELECT city, follower_count
    FROM follower_city_snapshots
    WHERE pulled_at_utc = ?
    """, (latest_ts,)).fetchall()

    prev_map = {}
    if prev_ts:
        prev_rows = conn.execute("""
        SELECT city, follower_count
        FROM follower_city_snapshots
        WHERE pulled_at_utc = ?
        """, (prev_ts,)).fetchall()
        prev_map = {r[0]: int(r[1]) for r in prev_rows}

    for r in latest_rows:
        city = r[0]
        cur = int(r[1])
        prev = prev_map.get(city)
        delta = (cur - prev) if prev is not None else None
        followers_city.append({"city": city, "followers": cur})
        followers_city_delta.append({"city": city, "followers": cur, "delta_since_last_pull": delta})

    followers_city.sort(key=lambda x: x["followers"], reverse=True)
    followers_city_delta.sort(key=lambda x: x["followers"], reverse=True)

# Build daily follower history (last value per day)
raw = conn.execute("""
SELECT pulled_at_utc, follower_count
FROM follower_snapshots
ORDER BY pulled_at_utc ASC, id ASC
""").fetchall()

by_day = {}
for r in raw:
    day = (r["pulled_at_utc"] or "")[:10]
    by_day[day] = int(r["follower_count"])

days = sorted(by_day.keys())
follower_history = []
prev = None
for d in days:
    cur = by_day[d]
    delta = None if prev is None else cur - prev
    follower_history.append({"day": d, "followers": cur, "followers_per_day": delta})
    prev = cur

baseline = None
if latest_follow:
    latest_dt = datetime.fromisoformat(latest_follow["pulled_at_utc"])
    cutoff = (latest_dt - timedelta(hours=24)).isoformat()
    baseline = conn.execute(
        "SELECT * FROM follower_snapshots WHERE pulled_at_utc <= ? ORDER BY pulled_at_utc DESC, id DESC LIMIT 1",
        (cutoff,),
    ).fetchone()

raw_campaign_rows = []
raw_ad_rows = []
breakdowns = {}
meta_pulled_at = None
for r in latest_by_level:
    level = r["level"]
    rows = json.loads(r["payload_json"])
    meta_pulled_at = meta_pulled_at or r["pulled_at_utc"]
    if level == "campaign":
        raw_campaign_rows = rows
    elif level == "ad":
        raw_ad_rows = rows
    elif "__" in level:
        breakdowns[level] = rows

campaign_rows = aggregate_campaign(raw_campaign_rows)
ad_rows = aggregate_ads(raw_ad_rows)

insights = []
if latest_follow:
    insights.append(f"Follower snapshot: {latest_follow['follower_count']:,} at {latest_follow['pulled_at_utc']} UTC.")
if baseline and latest_follow:
    d24 = int(latest_follow["follower_count"]) - int(baseline["follower_count"])
    insights.append(f"24h follower change: {d24:+,}.")
if campaign_rows:
    insights.append(f"Meta API loaded: {len(campaign_rows)} campaign(s). Click a campaign to view ad-level CPC breakdown.")
else:
    insights.append("Ads API snapshots missing (awaiting Meta API pull).")

# Normalize selected expanded breakdown keys for downstream dashboards
norm_breakdowns = {
    "country": breakdowns.get("ad__country", []),
    "region": breakdowns.get("ad__region", []),
    "age_gender": breakdowns.get("ad__age_gender", []),
    "placement": breakdowns.get("ad__publisher_platform_platform_position", []),
    "device": breakdowns.get("ad__impression_device", []),
}

payload = {
    "updated_at": (latest_follow["pulled_at_utc"] if latest_follow else None) or meta_pulled_at,
    "campaign": campaign_rows,
    "ad": ad_rows,
    "breakdowns": norm_breakdowns,
    "followers": {
        "current": int(latest_follow["follower_count"]) if latest_follow else None,
        "username": latest_follow["username"] if latest_follow else None,
        "source": latest_follow["source"] if latest_follow else None,
        "pulled_at": latest_follow["pulled_at_utc"] if latest_follow else None,
        "updated_at": latest_follow["pulled_at_utc"] if latest_follow else None,
        "delta_24h": (int(latest_follow["follower_count"]) - int(baseline["follower_count"])) if latest_follow and baseline else None,
    },
    "followers_city": followers_city,
    "followers_city_delta": followers_city_delta,
    "followers_history": follower_history,
    "insights": insights,
}

OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"wrote {OUT}")
