#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="$BASE_DIR/config/defaults.json"

err() { echo "[pipeline] ERROR: $*" >&2; }
log() { echo "[pipeline] $*"; }
require_bin() { command -v "$1" >/dev/null 2>&1 || { err "Missing dependency: $1"; exit 2; }; }

usage() {
  cat <<EOF
Usage: $0 <input-video-file> [run-name]
EOF
}

INPUT_FILE="${1:-}"
RUN_NAME="${2:-run_$(date +%Y%m%d_%H%M%S)}"

if [[ -z "$INPUT_FILE" ]]; then
  usage
  exit 1
fi
[[ -f "$INPUT_FILE" ]] || { err "Input file not found: $INPUT_FILE"; exit 1; }

require_bin ffmpeg
require_bin ffprobe
require_bin python3

if command -v whisper >/dev/null 2>&1; then
  log "Whisper CLI detected (preferred)"
elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
  log "Whisper CLI not found; using OPENAI_API_KEY fallback"
else
  err "Neither local 'whisper' CLI nor OPENAI_API_KEY is available for transcription"
  exit 3
fi

RUN_DIR_PROCESSING="$BASE_DIR/processing/$RUN_NAME"
RUN_DIR_OUTPUT="$BASE_DIR/outputs/$RUN_NAME"
RUN_DIR_LOGS="$BASE_DIR/logs/$RUN_NAME"
mkdir -p "$RUN_DIR_PROCESSING" "$RUN_DIR_OUTPUT" "$RUN_DIR_LOGS"

INPUT_ABS="$(cd "$(dirname "$INPUT_FILE")" && pwd)/$(basename "$INPUT_FILE")"
BASENAME="$(basename "$INPUT_FILE")"
STEM="${BASENAME%.*}"
WORK_INPUT="$RUN_DIR_PROCESSING/$BASENAME"
cp "$INPUT_ABS" "$WORK_INPUT"

get_cfg() {
  python3 - "$CONFIG_FILE" "$1" <<'PY'
import json,sys
cfg=json.load(open(sys.argv[1]))
key=sys.argv[2]
parts=key.split('.')
cur=cfg
for p in parts:
  cur=cur.get(p,{}) if isinstance(cur,dict) else {}
print(cur if cur != {} else "")
PY
}

WHISPER_MODEL="$(get_cfg transcription.model)"
WHISPER_LANG="$(get_cfg transcription.language)"
MIN_DUR="$(get_cfg qa.min_duration_seconds)"
MAX_DUR="$(get_cfg qa.max_duration_seconds)"
TARGET_LOUD="$(get_cfg qa.target_loudness_db)"
MAX_SILENCE="$(get_cfg qa.max_silence_ratio)"

[[ -n "$WHISPER_MODEL" ]] || WHISPER_MODEL="base"
[[ -n "$MIN_DUR" ]] || MIN_DUR="10"
[[ -n "$MAX_DUR" ]] || MAX_DUR="90"
[[ -n "$TARGET_LOUD" ]] || TARGET_LOUD="-16"
[[ -n "$MAX_SILENCE" ]] || MAX_SILENCE="0.35"

TRANSCRIPT_BASE="$RUN_DIR_PROCESSING/$STEM.transcript"
TRANSCRIPT_JSON="$TRANSCRIPT_BASE.json"
TRANSCRIPT_SRT="$TRANSCRIPT_BASE.srt"
QA_JSON="$RUN_DIR_LOGS/$STEM.qa.json"
SUMMARY_JSON="$RUN_DIR_LOGS/$STEM.run_summary.json"

log "[1/3] Transcribing..."
TRANSCRIBE_CMD=(python3 "$BASE_DIR/scripts/transcribe_whisper.py" --input "$WORK_INPUT" --output-base "$TRANSCRIPT_BASE" --model "$WHISPER_MODEL")
if [[ -n "$WHISPER_LANG" ]]; then
  TRANSCRIBE_CMD+=(--language "$WHISPER_LANG")
fi
"${TRANSCRIBE_CMD[@]}" | tee "$RUN_DIR_LOGS/transcribe.log"

log "[2/3] Rendering variants..."
"$BASE_DIR/scripts/render_variants_ffmpeg.sh" "$WORK_INPUT" "$RUN_DIR_OUTPUT" "$STEM" | tee "$RUN_DIR_LOGS/render.log"

log "[3/3] QA scoring..."
python3 "$BASE_DIR/scripts/qa_score.py" \
  --input "$RUN_DIR_OUTPUT/${STEM}_9x16.mp4" \
  --output "$QA_JSON" \
  --srt "$TRANSCRIPT_SRT" \
  --min-duration "$MIN_DUR" \
  --max-duration "$MAX_DUR" \
  --target-loudness "$TARGET_LOUD" \
  --max-silence-ratio "$MAX_SILENCE" | tee "$RUN_DIR_LOGS/qa.log"

python3 - "$SUMMARY_JSON" "$INPUT_ABS" "$RUN_NAME" "$RUN_DIR_OUTPUT" "$TRANSCRIPT_JSON" "$TRANSCRIPT_SRT" "$QA_JSON" "$STEM" <<'PY'
import json,sys
summary={
  'input': sys.argv[2],
  'run_name': sys.argv[3],
  'output_dir': sys.argv[4],
  'transcript_json': sys.argv[5],
  'subtitle_srt': sys.argv[6],
  'qa_json': sys.argv[7],
  'rendered_files': [
    f"{sys.argv[4]}/{sys.argv[8]}_9x16.mp4",
    f"{sys.argv[4]}/{sys.argv[8]}_1x1.mp4",
    f"{sys.argv[4]}/{sys.argv[8]}_16x9.mp4",
  ]
}
open(sys.argv[1],'w').write(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
PY

log "Pipeline complete"
log "Summary: $SUMMARY_JSON"
