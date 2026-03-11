#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROCESSING_DIR="$BASE_DIR/processing"
OUTPUT_DIR="$BASE_DIR/outputs"
LOG_DIR="$BASE_DIR/logs"

mkdir -p "$PROCESSING_DIR" "$OUTPUT_DIR" "$LOG_DIR"

INPUT_FILE="${1:-}"
if [[ -z "$INPUT_FILE" ]]; then
  echo "Usage: $0 <input-video-file>"
  exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
  echo "Input file not found: $INPUT_FILE"
  exit 1
fi

BASENAME="$(basename "$INPUT_FILE")"
WORK_INPUT="$PROCESSING_DIR/$BASENAME"
cp "$INPUT_FILE" "$WORK_INPUT"

echo "[1/3] Transcription stub..."
python3 "$BASE_DIR/scripts/transcribe_whisper.py" --input "$WORK_INPUT" --output "$PROCESSING_DIR/${BASENAME%.*}.transcript.json"

echo "[2/3] Render aspect variants..."
"$BASE_DIR/scripts/render_variants_ffmpeg.sh" "$WORK_INPUT" "$OUTPUT_DIR"

echo "[3/3] QA placeholder scoring..."
python3 "$BASE_DIR/scripts/qa_score.py" --input "$WORK_INPUT" --output "$LOG_DIR/${BASENAME%.*}.qa.json"

echo "Pipeline complete. Outputs in: $OUTPUT_DIR"
