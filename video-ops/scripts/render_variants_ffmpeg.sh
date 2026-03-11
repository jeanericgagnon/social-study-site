#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="${1:-}"
OUTPUT_DIR="${2:-}"

if [[ -z "$INPUT_FILE" || -z "$OUTPUT_DIR" ]]; then
  echo "Usage: $0 <input-video-file> <output-dir>"
  exit 1
fi

mkdir -p "$OUTPUT_DIR"

NAME="$(basename "$INPUT_FILE")"
STEM="${NAME%.*}"

ffmpeg -y -i "$INPUT_FILE" -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -c:a aac "$OUTPUT_DIR/${STEM}_9x16.mp4"
ffmpeg -y -i "$INPUT_FILE" -vf "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -c:a aac "$OUTPUT_DIR/${STEM}_1x1.mp4"
ffmpeg -y -i "$INPUT_FILE" -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" -c:v libx264 -c:a aac "$OUTPUT_DIR/${STEM}_16x9.mp4"

echo "Rendered 3 variants to $OUTPUT_DIR"
