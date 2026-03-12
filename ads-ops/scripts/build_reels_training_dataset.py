#!/usr/bin/env python3
"""Build unified IG reels training dataset for thesocial.study.

Joins:
- Manifest metadata
- Transcript presence/content
- Visual diagnostics
- IG Graph media insights (where available)

Outputs:
- exports/instagram/thesocial.study/reels/reels_training_dataset_latest.json
- exports/instagram/thesocial.study/reels/reels_training_dataset_latest.csv
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

WORKSPACE = Path("/Users/ericsysclaw/.openclaw/workspace")
REELS_DIR = WORKSPACE / "exports" / "instagram" / "thesocial.study" / "reels"
MANIFEST_PATH = REELS_DIR / "manifest_latest.json"
VISUAL_PATH = REELS_DIR / "visual_diagnostics_latest.json"
TRANSCRIPTS_DIR = REELS_DIR / "transcripts"
CONFIG_PATH = WORKSPACE / "exports" / "meta-ads" / "config.json"

OUT_JSON = REELS_DIR / "reels_training_dataset_latest.json"
OUT_CSV = REELS_DIR / "reels_training_dataset_latest.csv"

GRAPH_BASE = "https://graph.facebook.com/v25.0"

TARGET_METRICS = [
    "views",
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "plays",
    "impressions",
    "video_views",
    "total_interactions",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
]

SUPPORTED_METRICS_BATCH = [
    "views",
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "total_interactions",
    "ig_reels_avg_watch_time",
    "ig_reels_video_view_total_time",
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def get_ig_user_id(token: str) -> str:
    r = requests.get(
        f"{GRAPH_BASE}/me/accounts",
        params={
            "access_token": token,
            "fields": "id,name,instagram_business_account",
            "limit": 100,
        },
        timeout=60,
    )
    r.raise_for_status()
    pages = r.json().get("data", [])
    for page in pages:
        ig = (page.get("instagram_business_account") or {}).get("id")
        if ig:
            return str(ig)
    raise RuntimeError("No instagram_business_account linked to accessible pages")


def fetch_metrics_for_media(media_id: str, token: str) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    """Returns (metrics, missing_reason_by_metric, api_errors)."""
    metrics: dict[str, Any] = {k: None for k in TARGET_METRICS}
    missing_reason: dict[str, str] = {}
    api_errors: list[str] = []

    # First: fetch the currently supported batch in one call (fewer writes / lower rate pressure)
    r = requests.get(
        f"{GRAPH_BASE}/{media_id}/insights",
        params={"access_token": token, "metric": ",".join(SUPPORTED_METRICS_BATCH)},
        timeout=60,
    )
    if r.status_code == 200:
        data = r.json().get("data", [])
        seen = set()
        for row in data:
            name = row.get("name")
            values = row.get("values") or []
            val = values[0].get("value") if values else None
            if name in metrics:
                metrics[name] = val
                seen.add(name)
        for m in SUPPORTED_METRICS_BATCH:
            if m not in seen:
                missing_reason[m] = "metric_not_returned"
    else:
        err = r.json().get("error", {}) if "application/json" in r.headers.get("Content-Type", "") else {}
        msg = err.get("message") or f"HTTP {r.status_code}"
        api_errors.append(f"batch_supported_metrics_failed: {msg}")
        for m in SUPPORTED_METRICS_BATCH:
            missing_reason[m] = f"api_error: {msg}"

    # Then probe known deprecated/unsupported metrics individually so we can label blockers clearly.
    for m in ["plays", "impressions", "video_views"]:
        r = requests.get(
            f"{GRAPH_BASE}/{media_id}/insights",
            params={"access_token": token, "metric": m},
            timeout=60,
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            if data:
                values = data[0].get("values") or []
                metrics[m] = values[0].get("value") if values else None
                if metrics[m] is None:
                    missing_reason[m] = "metric_empty"
            else:
                missing_reason[m] = "metric_not_returned"
            continue

        err = r.json().get("error", {}) if "application/json" in r.headers.get("Content-Type", "") else {}
        msg = err.get("message") or f"HTTP {r.status_code}"
        lmsg = msg.lower()
        if "no longer supported" in lmsg:
            missing_reason[m] = "deprecated_in_graph_v22_plus"
        elif "does not support" in lmsg:
            missing_reason[m] = "unsupported_for_media_product_type"
        else:
            missing_reason[m] = f"api_error: {msg}"
        api_errors.append(f"metric_{m}_failed: {msg}")

    return metrics, missing_reason, api_errors


def main() -> None:
    manifest = load_json(MANIFEST_PATH)
    visual = load_json(VISUAL_PATH)
    cfg = load_json(CONFIG_PATH)

    token = (cfg.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Missing access_token in exports/meta-ads/config.json")

    ig_user_id = get_ig_user_id(token)

    visual_by_id = {str(r.get("media_id")): r for r in visual.get("rows", [])}

    output_rows: list[dict[str, Any]] = []

    for row in manifest.get("rows", []):
        media_id = str(row.get("media_id") or "")
        if not media_id:
            continue

        transcript_path = TRANSCRIPTS_DIR / f"{media_id}.txt"
        transcript_exists = transcript_path.exists()
        transcript_text = transcript_path.read_text().strip() if transcript_exists else ""

        visual_row = visual_by_id.get(media_id) or {}

        metrics, missing_reason, api_errors = fetch_metrics_for_media(media_id, token)

        data_quality_flags = []
        if not transcript_exists:
            data_quality_flags.append("missing_transcript")
        if not visual_row:
            data_quality_flags.append("missing_visual_diagnostics")
        if api_errors:
            data_quality_flags.append("api_partial_or_errors")
        if all(metrics.get(k) is None for k in TARGET_METRICS):
            data_quality_flags.append("missing_all_performance_metrics")

        joined = {
            "media_id": media_id,
            "permalink": row.get("permalink"),
            "timestamp": row.get("timestamp"),
            "caption": row.get("caption"),
            "media_type": row.get("media_type"),
            "media_product_type": row.get("media_product_type"),
            "transcript_path": str(transcript_path.relative_to(WORKSPACE)) if transcript_exists else None,
            "transcript_text_present": bool(transcript_text),
            "transcript_char_count": len(transcript_text),
            "visual": {
                "duration_s": visual_row.get("duration_s"),
                "resolution": visual_row.get("resolution"),
                "bitrate_mbps": visual_row.get("bitrate_mbps"),
                "scene_cuts": visual_row.get("scene_cuts"),
                "cuts_per_min": visual_row.get("cuts_per_min"),
            },
            "performance": metrics,
            "data_quality_flags": data_quality_flags,
            "missing_reason": missing_reason,
            "api_errors": api_errors,
        }
        output_rows.append(joined)

    # Coverage summary
    missing_counts = {}
    for metric in TARGET_METRICS:
        missing_counts[metric] = sum(1 for r in output_rows if r["performance"].get(metric) is None)

    reels_with_any_performance = sum(
        1
        for r in output_rows
        if any(r["performance"].get(m) is not None for m in TARGET_METRICS)
    )

    blocker_counts: dict[str, int] = {}
    for r in output_rows:
        for reason in r.get("missing_reason", {}).values():
            blocker_counts[reason] = blocker_counts.get(reason, 0) + 1

    top_blockers = sorted(blocker_counts.items(), key=lambda kv: kv[1], reverse=True)[:8]

    payload = {
        "generated_at": now_utc_iso(),
        "target_username": manifest.get("target_username"),
        "ig_user_id": ig_user_id,
        "total_reels": len(output_rows),
        "coverage": {
            "reels_with_performance_metrics": reels_with_any_performance,
            "reels_missing_each_key_metric": missing_counts,
            "top_blockers": [{"reason": r, "count": c} for r, c in top_blockers],
        },
        "rows": output_rows,
    }

    OUT_JSON.write_text(json.dumps(payload, indent=2))

    # CSV (flattened)
    csv_fields = [
        "media_id",
        "permalink",
        "timestamp",
        "media_type",
        "media_product_type",
        "caption",
        "transcript_path",
        "transcript_text_present",
        "transcript_char_count",
        "duration_s",
        "resolution",
        "bitrate_mbps",
        "scene_cuts",
        "cuts_per_min",
    ] + TARGET_METRICS + [
        "data_quality_flags",
        "missing_reason",
    ]

    with OUT_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields)
        w.writeheader()
        for r in output_rows:
            perf = r["performance"]
            vis = r["visual"]
            flat = {
                "media_id": r["media_id"],
                "permalink": r.get("permalink"),
                "timestamp": r.get("timestamp"),
                "media_type": r.get("media_type"),
                "media_product_type": r.get("media_product_type"),
                "caption": r.get("caption"),
                "transcript_path": r.get("transcript_path"),
                "transcript_text_present": r.get("transcript_text_present"),
                "transcript_char_count": r.get("transcript_char_count"),
                "duration_s": vis.get("duration_s"),
                "resolution": vis.get("resolution"),
                "bitrate_mbps": vis.get("bitrate_mbps"),
                "scene_cuts": vis.get("scene_cuts"),
                "cuts_per_min": vis.get("cuts_per_min"),
                "data_quality_flags": "|".join(r.get("data_quality_flags", [])),
                "missing_reason": json.dumps(r.get("missing_reason", {}), sort_keys=True),
            }
            flat.update({m: perf.get(m) for m in TARGET_METRICS})
            w.writerow(flat)

    print(
        json.dumps(
            {
                "ok": True,
                "out_json": str(OUT_JSON),
                "out_csv": str(OUT_CSV),
                "total_reels": len(output_rows),
                "reels_with_performance_metrics": reels_with_any_performance,
                "missing_counts": missing_counts,
                "top_blockers": [{"reason": r, "count": c} for r, c in top_blockers],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
