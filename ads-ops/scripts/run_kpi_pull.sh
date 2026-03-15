#!/usr/bin/env bash
set -euo pipefail
cd /Users/ericsysclaw/.openclaw/workspace

# Ensure Vercel sees a team-authorized git identity in deployment metadata.
export GIT_AUTHOR_NAME="Jean Eric Gagnon"
export GIT_AUTHOR_EMAIL="jean.eric.gagnon619@gmail.com"
export GIT_COMMITTER_NAME="Jean Eric Gagnon"
export GIT_COMMITTER_EMAIL="jean.eric.gagnon619@gmail.com"

if [ -f ads-ops/.env.meta ]; then
  set -a
  source ads-ops/.env.meta
  set +a
fi

. .venv-metaads/bin/activate

# Pull ads KPIs (script supports env OR exports/meta-ads/config.json fallback)
# Keep follower pipeline running even if ads token is temporarily invalid.
python ads-ops/scripts/pull_meta_to_sqlite.py || echo "WARN: ads pull failed; continuing with follower pulls"

# Pull follower demographics + IG media insights/reels (best-effort), then follower count fallback
python ads-ops/scripts/pull_ig_follower_demographics.py || true
python ads-ops/scripts/pull_ig_media_insights.py || true
python ads-ops/scripts/pull_ig_reels.py || true
python ads-ops/scripts/pull_followers_blastup.py
python ads-ops/scripts/build_latest_json.py

# Ensure yesterday exists in DB snapshots; if missing, force a short backfill pull
python3 - <<'PY'
import datetime,sqlite3,subprocess,os
DB='ads-ops/db/kpi.sqlite'
yday=(datetime.datetime.now(datetime.timezone.utc).date()-datetime.timedelta(days=1)).isoformat()
ok=False
try:
    conn=sqlite3.connect(DB)
    cur=conn.cursor()
    rows=cur.execute("""
      SELECT payload_json FROM kpi_snapshots
      WHERE source='meta_marketing_api' AND level IN ('campaign','ad','adset')
      ORDER BY id DESC LIMIT 3
    """).fetchall()
    blob='\n'.join(r[0] or '' for r in rows)
    ok=(yday in blob)
except Exception as e:
    print(f'WARN: backfill check failed: {e}')
finally:
    try: conn.close()
    except: pass
print(f'backfill_check yesterday={yday} present={ok}')
if not ok:
    print('backfill_action forcing short lookback pull (2 days)')
    env=os.environ.copy()
    env['META_LOOKBACK_DAYS']='2'
    subprocess.run(['python','ads-ops/scripts/pull_meta_to_sqlite.py'],env=env,check=False)
    subprocess.run(['python','ads-ops/scripts/build_latest_json.py'],check=False)
PY

# Deploy updated dashboard so site reflects every successful refresh (retry for transient Vercel errors)
(
  cd ads-ops/dashboard
  if command -v vercel >/dev/null 2>&1; then
    ok=0
    for i in 1 2 3; do
      if vercel --prod --yes --scope eric-gagnons-projects; then
        ok=1
        break
      fi
      echo "WARN: vercel deploy attempt $i failed"
      sleep 8
    done
    [ "$ok" -eq 1 ] || echo "WARN: vercel deploy failed after retries"
  else
    echo "WARN: vercel CLI not found; skipping deploy"
  fi
)

# Optional: trigger Vercel deploy hook after fresh data
if [ -n "${VERCEL_DEPLOY_HOOK_URL:-}" ]; then
  curl -fsS -X POST "$VERCEL_DEPLOY_HOOK_URL" >/dev/null || true
fi
