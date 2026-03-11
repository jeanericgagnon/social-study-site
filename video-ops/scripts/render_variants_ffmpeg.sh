#!/usr/bin/env bash
set -euo pipefail

if [[ "${TRACE:-0}" == "1" ]]; then set -x; fi

err() { echo "[render] ERROR: $*" >&2; }
log() { echo "[render] $*"; }

require_bin() {
  command -v "$1" >/dev/null 2>&1 || { err "missing dependency: $1"; exit 2; }
}

require_bin ffmpeg
require_bin ffprobe

INPUT_FILE="${1:-}"
OUTPUT_DIR="${2:-}"
BASENAME="${3:-}"

if [[ -z "$INPUT_FILE" || -z "$OUTPUT_DIR" ]]; then
  err "Usage: $0 <input-video-file> <output-dir> [basename]"
  exit 1
fi
[[ -f "$INPUT_FILE" ]] || { err "input not found: $INPUT_FILE"; exit 1; }

mkdir -p "$OUTPUT_DIR"

if [[ -z "$BASENAME" ]]; then
  NAME="$(basename "$INPUT_FILE")"
  BASENAME="${NAME%.*}"
fi

SRC_DIR="$(dirname "$INPUT_FILE")"
STEM="$(basename "$INPUT_FILE")"
STEM="${STEM%.*}"
SRT_CANDIDATE=""
for cand in "$SRC_DIR/${BASENAME}.srt" "$SRC_DIR/${STEM}.srt" "$SRC_DIR/${STEM}.transcript.srt"; do
  if [[ -f "$cand" ]]; then
    SRT_CANDIDATE="$cand"
    break
  fi
done

SUB_FILTER=""
HAS_SUB_FILTER=0
if ffmpeg -hide_banner -filters 2>/dev/null | grep -q " subtitles "; then
  HAS_SUB_FILTER=1
fi

if [[ -f "$SRT_CANDIDATE" ]]; then
  if [[ "$HAS_SUB_FILTER" == "1" ]]; then
    ESCAPED_SRT="${SRT_CANDIDATE//:/\\:}"
    SUB_FILTER=",subtitles=filename='${ESCAPED_SRT}'"
    log "burning subtitles from $SRT_CANDIDATE"
  else
    log "SRT found but ffmpeg lacks subtitles filter; rendering without burn-in"
  fi
else
  log "no SRT found, rendering without burned subtitles"
fi

AUDIO_FILTER="loudnorm=I=-16:LRA=11:TP=-1.5,acompressor=threshold=-18dB:ratio=2.5:attack=20:release=200:makeup=2"
COMMON_ARGS=(
  -y
  -hide_banner
  -loglevel error
  -i "$INPUT_FILE"
  -c:v libx264
  -preset medium
  -crf 20
  -pix_fmt yuv420p
  -movflags +faststart
  -c:a aac
  -b:a 192k
  -ar 48000
  -af "$AUDIO_FILTER"
)

render_one() {
  local label="$1" width="$2" height="$3"
  local vf="scale=${width}:${height}:force_original_aspect_ratio=decrease,pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:color=black${SUB_FILTER}"
  local out="$OUTPUT_DIR/${BASENAME}_${label}.mp4"

  log "rendering ${label} -> $out"
  ffmpeg "${COMMON_ARGS[@]}" -vf "$vf" "$out"
  [[ -s "$out" ]] || { err "output missing/empty: $out"; exit 3; }
}

render_one "9x16" 1080 1920
render_one "1x1" 1080 1080
render_one "16x9" 1920 1080

log "done: rendered 3 variants to $OUTPUT_DIR"
