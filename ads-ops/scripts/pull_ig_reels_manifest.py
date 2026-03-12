#!/usr/bin/env python3
"""Build a local manifest of Instagram reels/videos for thesocial.study.

Outputs:
  - exports/instagram/thesocial.study/reels/manifest_latest.json
  - exports/instagram/thesocial.study/reels/manifest_latest.csv
  - exports/instagram/thesocial.study/reels/discovery_latest.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests

WORKSPACE = Path("/Users/ericsysclaw/.openclaw/workspace")
META_CONFIG = WORKSPACE / "exports" / "meta-ads" / "config.json"
OUT_DIR = WORKSPACE / "exports" / "instagram" / "thesocial.study" / "reels"
MANIFEST_JSON = OUT_DIR / "manifest_latest.json"
MANIFEST_CSV = OUT_DIR / "manifest_latest.csv"
DISCOVERY_JSON = OUT_DIR / "discovery_latest.json"

API_VERSION = os.getenv("META_API_VERSION", "v25.0")
BASE = f"https://graph.facebook.com/{API_VERSION}"

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


class GraphError(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_token() -> str:
    env = (os.getenv("META_ACCESS_TOKEN") or "").strip()
    if env:
        return env
    if META_CONFIG.exists():
        cfg = json.loads(META_CONFIG.read_text())
        tok = (cfg.get("access_token") or "").strip()
        if tok:
            return tok
    raise SystemExit(
        "Missing META access token. Set META_ACCESS_TOKEN or exports/meta-ads/config.json:access_token"
    )


def get_json(url: str, params: Optional[Dict[str, str]] = None, timeout: int = 90) -> Dict:
    r = requests.get(url, params=params or {}, timeout=timeout)
    if r.status_code >= 400:
        try:
            body = r.json()
            msg = body.get("error", {}).get("message") or r.text
            code = body.get("error", {}).get("code")
            subcode = body.get("error", {}).get("error_subcode")
            raise GraphError(f"HTTP {r.status_code} code={code} subcode={subcode}: {msg}")
        except ValueError:
            raise GraphError(f"HTTP {r.status_code}: {r.text[:400]}")
    return r.json()


def get_all_pages(url: str, params: Dict[str, str]) -> List[Dict]:
    rows: List[Dict] = []
    cur_url = url
    cur_params: Dict[str, str] = dict(params)
    while True:
        body = get_json(cur_url, cur_params)
        rows.extend(body.get("data", []))
        nxt = body.get("paging", {}).get("next")
        if not nxt:
            return rows
        cur_url = nxt
        cur_params = {}


def discover_ig_account(token: str, preferred_username: str) -> Tuple[Dict, List[Dict], List[str]]:
    warnings: List[str] = []
    pages = get_all_pages(
        f"{BASE}/me/accounts",
        {
            "access_token": token,
            "fields": "id,name,instagram_business_account",
            "limit": "100",
        },
    )

    with_ig = [p for p in pages if (p.get("instagram_business_account") or {}).get("id")]
    if not with_ig:
        raise GraphError(
            "No accessible Facebook pages with instagram_business_account. "
            "Likely missing pages_show_list / pages_read_engagement or page not linked."
        )

    selected = with_ig[0]
    selected_ig_id = selected["instagram_business_account"]["id"]

    # Prefer target username if available among linked pages.
    for p in with_ig:
        ig_id = p["instagram_business_account"]["id"]
        try:
            ig_profile = get_json(
                f"{BASE}/{ig_id}",
                {
                    "access_token": token,
                    "fields": "id,username,name,followers_count,media_count",
                },
            )
        except Exception:
            continue
        if (ig_profile.get("username") or "").lower() == preferred_username.lower():
            selected = p
            selected_ig_id = ig_id
            break

    ig_profile = get_json(
        f"{BASE}/{selected_ig_id}",
        {
            "access_token": token,
            "fields": "id,username,name,followers_count,media_count,biography",
        },
    )

    discovered_username = (ig_profile.get("username") or "").lower()
    if discovered_username != preferred_username.lower():
        warnings.append(
            f"Target username '{preferred_username}' not matched exactly; discovered '{ig_profile.get('username')}'."
        )

    return {
        "page_id": selected.get("id"),
        "page_name": selected.get("name"),
        "ig_user_id": ig_profile.get("id"),
        "ig_username": ig_profile.get("username"),
        "ig_name": ig_profile.get("name"),
        "followers_count": ig_profile.get("followers_count"),
        "media_count": ig_profile.get("media_count"),
    }, pages, warnings


def load_existing_manifest() -> Dict[str, Dict]:
    if not MANIFEST_JSON.exists():
        return {}
    try:
        payload = json.loads(MANIFEST_JSON.read_text())
        rows = payload.get("rows", []) if isinstance(payload, dict) else []
        return {r.get("media_id"): r for r in rows if r.get("media_id")}
    except Exception:
        return {}


def build_rows(token: str, ig_user_id: str, existing: Dict[str, Dict]) -> Tuple[List[Dict], List[str]]:
    warnings: List[str] = []
    media_rows = get_all_pages(
        f"{BASE}/{ig_user_id}/media",
        {
            "access_token": token,
            "fields": (
                "id,caption,media_type,media_product_type,media_url,permalink,"
                "thumbnail_url,timestamp,username"
            ),
            "limit": "100",
        },
    )

    output: List[Dict] = []
    for m in media_rows:
        media_type = (m.get("media_type") or "").upper()
        product = (m.get("media_product_type") or "").upper()

        is_reel_or_video = media_type == "VIDEO" or product == "REELS"
        if not is_reel_or_video:
            continue

        media_id = m.get("id")
        media_url = (m.get("media_url") or "").strip()
        prev = existing.get(media_id, {})

        status = prev.get("download_status") or ("pending" if media_url else "no_media_url")
        if not media_url and status == "pending":
            status = "no_media_url"
        if media_url and status in {"no_media_url", "download_failed_no_media_url"}:
            status = "pending"

        row = {
            "media_id": media_id,
            "permalink": m.get("permalink") or "",
            "media_type": m.get("media_type") or "",
            "timestamp": m.get("timestamp") or "",
            "caption": m.get("caption") or "",
            "media_url": media_url,
            "media_url_available": bool(media_url),
            "download_status": status,
            "local_path": prev.get("local_path") or "",
            "media_product_type": m.get("media_product_type") or "",
            "username": m.get("username") or "",
            "thumbnail_url": m.get("thumbnail_url") or "",
        }
        output.append(row)

    if output and not any(r.get("media_url_available") for r in output):
        warnings.append(
            "No media_url values returned for video/reels. "
            "Likely token/app lacks instagram_basic on the connected IG business account."
        )

    output.sort(key=lambda r: r.get("timestamp") or "", reverse=True)
    return output, warnings


def write_csv(rows: Iterable[Dict]) -> None:
    MANIFEST_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull IG reels/video metadata manifest")
    parser.add_argument("--username", default="thesocial.study", help="Expected IG username")
    args = parser.parse_args()

    token = load_token()
    existing = load_existing_manifest()

    required_scopes = [
        "pages_show_list",
        "pages_read_engagement",
        "instagram_basic",
    ]

    discovery = {
        "generated_at": now_utc(),
        "target_username": args.username,
        "required_scopes": required_scopes,
        "warnings": [],
        "errors": [],
    }

    try:
        account, pages, warnings = discover_ig_account(token, args.username)
        discovery.update(account)
        discovery["accessible_page_count"] = len(pages)
        discovery["warnings"].extend(warnings)

        rows, more_warnings = build_rows(token, account["ig_user_id"], existing)
        discovery["warnings"].extend(more_warnings)

        payload = {
            "generated_at": now_utc(),
            "target_username": args.username,
            "ig_user_id": account.get("ig_user_id"),
            "ig_username": account.get("ig_username"),
            "required_scopes": required_scopes,
            "row_count": len(rows),
            "rows": rows,
        }

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        MANIFEST_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        write_csv(rows)
        DISCOVERY_JSON.write_text(json.dumps(discovery, indent=2, ensure_ascii=False))

        print(
            json.dumps(
                {
                    "ok": True,
                    "ig_user_id": account.get("ig_user_id"),
                    "ig_username": account.get("ig_username"),
                    "rows": len(rows),
                    "media_url_available": sum(1 for r in rows if r.get("media_url_available")),
                    "manifest_json": str(MANIFEST_JSON),
                    "manifest_csv": str(MANIFEST_CSV),
                    "discovery": str(DISCOVERY_JSON),
                },
                indent=2,
            )
        )
    except Exception as e:
        discovery["errors"].append(str(e))
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        DISCOVERY_JSON.write_text(json.dumps(discovery, indent=2, ensure_ascii=False))
        print(json.dumps({"ok": False, "error": str(e), "discovery": str(DISCOVERY_JSON)}, indent=2))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
