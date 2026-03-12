# IG Reels Ingestion + Download Pipeline (Phase 2 foundation)

This pipeline discovers and ingests reel/video metadata from the connected Instagram Business account, then downloads accessible media files locally.

Target account: `thesocial.study`

## Scripts

- `ads-ops/scripts/pull_ig_reels_manifest.py`
  - Discovers page + linked IG business account from existing Meta token
  - Pulls media metadata and filters to reels/video
  - Writes manifest JSON/CSV + discovery report
- `ads-ops/scripts/download_ig_reels_media.py`
  - Downloads files for rows where `media_url` is available
  - Idempotent: skips already-downloaded files and updates statuses

## Output locations

- `exports/instagram/thesocial.study/reels/manifest_latest.json`
- `exports/instagram/thesocial.study/reels/manifest_latest.csv`
- `exports/instagram/thesocial.study/reels/discovery_latest.json`
- `exports/instagram/thesocial.study/reels/download_latest.json`
- `exports/instagram/thesocial.study/reels/media/*`

Manifest fields include at least:
- `media_id`
- `permalink`
- `media_type`
- `timestamp`
- `caption`
- `media_url_available`
- `download_status`
- `local_path`

## Required token/scopes

Use either:
- `META_ACCESS_TOKEN` env var, or
- `exports/meta-ads/config.json` with `access_token`

Recommended scopes for this pipeline:
- `pages_show_list`
- `pages_read_engagement`
- `instagram_basic`

If `media_url` is not returned, downloads cannot proceed and rows are marked `download_failed_no_media_url`.

## Run

From workspace root (recommended interpreter includes `requests`):

```bash
./.venv-metaads/bin/python ads-ops/scripts/pull_ig_reels_manifest.py --username thesocial.study
./.venv-metaads/bin/python ads-ops/scripts/download_ig_reels_media.py
```

If your active Python already has `requests`, plain `python3` also works.

Optional (test small batch):

```bash
python3 ads-ops/scripts/download_ig_reels_media.py --limit 5
```

## Idempotency/safety

- Existing files are not overwritten; they are marked `downloaded_exists`.
- Manifest is updated in place so future runs continue from prior status.
- Failures are recorded per-media in `download_latest.json` and `download_status`.
