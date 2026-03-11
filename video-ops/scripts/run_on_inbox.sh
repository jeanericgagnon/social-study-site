#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INBOX_DIR="$BASE_DIR/inbox"

latest="$(find "$INBOX_DIR" -maxdepth 1 -type f \( -iname '*.mp4' -o -iname '*.mov' -o -iname '*.mkv' -o -iname '*.m4v' \) -print0 | xargs -0 ls -t 2>/dev/null | head -n 1 || true)"

if [[ -z "$latest" ]]; then
  echo "[run_on_inbox] No video files found in $INBOX_DIR"
  exit 1
fi

echo "[run_on_inbox] Processing newest file: $latest"
"$BASE_DIR/scripts/run_pipeline.sh" "$latest"
