#!/usr/bin/env bash
set -euo pipefail

# Safe wrapper for URL/local transcription via OpenAI Whisper API
# - YouTube allowlist for URL mode
# - Explicit upload approval required
# - Stores output under ~/Documents/transcripts/whisper

usage() {
  cat >&2 <<'EOF'
Usage:
  run-safe.sh <youtube-url|local-media-file> [--approve-openai-upload] [--allow-local-file] [--out /path/out.txt] [--language en] [--json]
EOF
  exit 2
}

[[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage

INPUT="$1"; shift || true
APPROVE="false"
ALLOW_LOCAL="false"
OUT=""
LANG=""
JSON="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --approve-openai-upload) APPROVE="true"; shift ;;
    --allow-local-file) ALLOW_LOCAL="true"; shift ;;
    --out) OUT="${2:-}"; shift 2 ;;
    --language) LANG="${2:-}"; shift 2 ;;
    --json) JSON="true"; shift ;;
    *) echo "Unknown arg: $1" >&2; usage ;;
  esac
done

if [[ "$APPROVE" != "true" ]]; then
  echo "Blocked: missing --approve-openai-upload"
  echo "Reason: audio is uploaded to OpenAI transcription API."
  exit 3
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "Blocked: OPENAI_API_KEY is required"
  exit 4
fi

WORK_DIR="${HOME}/Documents/transcripts/whisper"
mkdir -p "$WORK_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
TMP_AUDIO="$WORK_DIR/input-${TS}.m4a"

if [[ "$INPUT" =~ ^https?:// ]]; then
  if [[ ! "$INPUT" =~ ^https?://(www\.)?(youtube\.com|youtu\.be)/ ]]; then
    echo "Blocked: URL mode only supports YouTube links"
    exit 5
  fi
  command -v yt-dlp >/dev/null 2>&1 || { echo "yt-dlp not found"; exit 6; }
  yt-dlp --extract-audio --audio-format m4a --audio-quality 0 --output "$TMP_AUDIO" "$INPUT"
  SRC="$TMP_AUDIO"
else
  if [[ "$ALLOW_LOCAL" != "true" ]]; then
    echo "Blocked: local file mode requires --allow-local-file"
    exit 7
  fi
  [[ -f "$INPUT" ]] || { echo "File not found: $INPUT"; exit 8; }
  SRC="$INPUT"
fi

if [[ -z "$OUT" ]]; then
  base="$WORK_DIR/transcript-${TS}"
  if [[ "$JSON" == "true" ]]; then OUT="${base}.json"; else OUT="${base}.txt"; fi
fi

CMD=("/opt/homebrew/lib/node_modules/openclaw/skills/openai-whisper-api/scripts/transcribe.sh" "$SRC" "--out" "$OUT")
[[ -n "$LANG" ]] && CMD+=("--language" "$LANG")
[[ "$JSON" == "true" ]] && CMD+=("--json")

umask 077
"${CMD[@]}"
echo "Saved: $OUT"
