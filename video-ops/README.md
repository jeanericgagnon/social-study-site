# video-ops (working local v1)

Local, no-voiceover video pipeline:
1) Transcribe with Whisper (local-first)
2) Render 3 aspect-ratio variants with ffmpeg
3) Run practical QA scoring

## Requirements

Required:
- `ffmpeg`
- `ffprobe`
- `python3`

Transcription backend (one required):
- Preferred: local `whisper` CLI (`pip install openai-whisper`)
- Fallback: `OPENAI_API_KEY` for OpenAI Whisper API

## Directory layout

- `inbox/` source clips
- `processing/` per-run working files
- `outputs/` per-run rendered variants
- `logs/` per-run logs + QA + summary JSON
- `scripts/` pipeline scripts
- `config/defaults.json` runtime defaults

## Quick start

```bash
cd video-ops
chmod +x scripts/*.sh

# run full pipeline on one file
./scripts/run_pipeline.sh inbox/clip.mp4

# run newest video in inbox
./scripts/run_on_inbox.sh
```

## What the pipeline produces

For each run (`run_YYYYMMDD_HHMMSS`):
- `processing/<run>/`
  - copied input media
  - `<stem>.transcript.json`
  - `<stem>.transcript.srt`
- `outputs/<run>/`
  - `<stem>_9x16.mp4`
  - `<stem>_1x1.mp4`
  - `<stem>_16x9.mp4`
- `logs/<run>/`
  - `transcribe.log`
  - `render.log`
  - `qa.log`
  - `<stem>.qa.json`
  - `<stem>.run_summary.json`

## Script details

### `scripts/transcribe_whisper.py`
- Uses local `whisper` CLI first if available.
- If local Whisper is unavailable, uses OpenAI API only when `OPENAI_API_KEY` exists.
- Fails clearly if neither backend is available.
- Writes both transcript JSON and SRT.

Example:
```bash
python3 scripts/transcribe_whisper.py \
  --input inbox/clip.mp4 \
  --output-base processing/clip.transcript \
  --model base
```

### `scripts/render_variants_ffmpeg.sh`
Inputs:
```bash
./scripts/render_variants_ffmpeg.sh <input-video> <output-dir> [basename]
```
- Renders 9:16, 1:1, 16:9 using scale+pad
- Burns subtitles when matching SRT exists beside input
- Applies audio normalization + light compression

### `scripts/qa_score.py`
Checks:
- duration bounds
- average loudness (via ffmpeg volumedetect)
- silence ratio (via silencedetect)
- subtitle presence

Outputs JSON with:
- `score` (0-100)
- `reasons` list
- metrics block

## Config

`config/defaults.json` stores defaults used by pipeline orchestration:
- transcription model/language
- QA thresholds (duration, loudness target, silence ratio)
- render profile metadata

## Troubleshooting

- **"Missing dependency: ffmpeg/ffprobe/python3"**
  - Install required tools and retry.

- **"Neither local 'whisper' CLI nor OPENAI_API_KEY is available"**
  - Install local Whisper (`pip install openai-whisper`) OR export API key:
    ```bash
    export OPENAI_API_KEY=...
    ```

- **No burned subtitles**
  - Ensure transcript step generated `.srt` and it exists in the processing run folder.

- **QA score is low**
  - Check `logs/<run>/<stem>.qa.json` reasons list for specific failures.
