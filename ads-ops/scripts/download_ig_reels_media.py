#!/usr/bin/env python3
"""Download IG reels/videos listed in manifest_latest.json.

Idempotent behavior:
- Skip files already present
- Preserve previously downloaded paths
- Update manifest download_status/local_path in place
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

import requests

WORKSPACE = Path("/Users/ericsysclaw/.openclaw/workspace")
OUT_DIR = WORKSPACE / "exports" / "instagram" / "thesocial.study" / "reels"
MANIFEST_JSON = OUT_DIR / "manifest_latest.json"
MANIFEST_CSV = OUT_DIR / "manifest_latest.csv"
MEDIA_DIR = OUT_DIR / "media"
DOWNLOAD_REPORT = OUT_DIR / "download_latest.json"

CSV_FIELDS = [
    "media_id",
    "permalink",
    "media_type",
    "timestamp",
    "caption",
    "media_url_available",
    "download_status",
    "local_path",
    "media_product_type",
    "username",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def file_ext_from_url(url: str, default: str = ".mp4") -> str:
    try:
        path = urlparse(url).path or ""
        suffix = Path(path).suffix.lower()
        if suffix and len(suffix) <= 8:
            return suffix
    except Exception:
        pass
    return default


def write_csv(rows: List[Dict]) -> None:
    with MANIFEST_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})


def download_to_path(url: str, path: Path, timeout: int = 120) -> None:
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 128):
                if chunk:
                    f.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download reels media from manifest")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of download attempts")
    args = parser.parse_args()

    if not MANIFEST_JSON.exists():
        raise SystemExit(f"Manifest not found: {MANIFEST_JSON}. Run pull_ig_reels_manifest.py first.")

    payload = json.loads(MANIFEST_JSON.read_text())
    rows: List[Dict] = payload.get("rows", [])

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)

    stats = {
        "generated_at": now_utc(),
        "total_rows": len(rows),
        "eligible": 0,
        "downloaded": 0,
        "skipped_existing": 0,
        "no_media_url": 0,
        "failed": 0,
        "errors": [],
    }

    attempts = 0
    for row in rows:
        media_id = row.get("media_id")
        media_url = (row.get("media_url") or "").strip()

        if not media_url:
            row["download_status"] = "download_failed_no_media_url"
            stats["no_media_url"] += 1
            continue

        stats["eligible"] += 1
        if args.limit and attempts >= args.limit:
            continue
        attempts += 1

        ext = file_ext_from_url(media_url)
        filename = f"{media_id}{ext}"
        out_path = MEDIA_DIR / filename

        if out_path.exists() and out_path.stat().st_size > 0:
            row["download_status"] = "downloaded_exists"
            row["local_path"] = str(out_path.relative_to(WORKSPACE))
            stats["skipped_existing"] += 1
            continue

        try:
            download_to_path(media_url, out_path)
            row["download_status"] = "downloaded"
            row["local_path"] = str(out_path.relative_to(WORKSPACE))
            stats["downloaded"] += 1
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", "unknown")
            row["download_status"] = f"download_failed_http_{code}"
            stats["failed"] += 1
            stats["errors"].append({"media_id": media_id, "error": str(e)})
        except Exception as e:
            row["download_status"] = "download_failed_exception"
            stats["failed"] += 1
            stats["errors"].append({"media_id": media_id, "error": str(e)})

    payload["download_last_run_at"] = now_utc()
    payload["rows"] = rows
    MANIFEST_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    write_csv(rows)
    DOWNLOAD_REPORT.write_text(json.dumps(stats, indent=2, ensure_ascii=False))

    print(json.dumps({"ok": True, **stats, "manifest": str(MANIFEST_JSON)}, indent=2))


if __name__ == "__main__":
    main()
