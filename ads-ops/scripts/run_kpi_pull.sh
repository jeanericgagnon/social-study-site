#!/usr/bin/env bash
set -euo pipefail
cd /Users/ericsysclaw/.openclaw/workspace

if [ -f ads-ops/.env.meta ]; then
  set -a
  source ads-ops/.env.meta
  set +a
fi

. .venv-metaads/bin/activate

# Pull ads KPIs (script supports env OR exports/meta-ads/config.json fallback)
python ads-ops/scripts/pull_meta_to_sqlite.py

# Pull follower demographics from IG Graph API (best-effort), then follower count fallback
python ads-ops/scripts/pull_ig_follower_demographics.py || true
python ads-ops/scripts/pull_followers_blastup.py
python ads-ops/scripts/build_latest_json.py

# Optional: trigger Vercel deploy hook after fresh data
if [ -n "${VERCEL_DEPLOY_HOOK_URL:-}" ]; then
  curl -fsS -X POST "$VERCEL_DEPLOY_HOOK_URL" >/dev/null || true
fi
