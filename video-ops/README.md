# video-ops (v1 scaffold)

Local video editing automation scaffold (no voiceover yet).

## Workflow
- Drop source clips in `inbox/`
- Run `./scripts/run_pipeline.sh <input-file>`
- Inspect outputs in `outputs/` and QA/transcript artifacts in `logs/` or `processing/`

## Directory layout
- `inbox/` raw source clips
- `processing/` working files
- `outputs/` rendered variants
- `archive/` completed source files
- `logs/` QA and pipeline logs
- `templates/` caption/hook templates
- `scripts/` automation scripts
- `config/` defaults and pipeline settings

## Config defaults
See `config/defaults.json`:
- formats: 9:16, 1:1, 16:9
- hook variants: 2
- caption style: basic
- qa thresholds: placeholder baseline gates

## Commands
```bash
./scripts/run_pipeline.sh inbox/clip.mp4
python3 scripts/transcribe_whisper.py --input inbox/clip.mp4 --output logs/clip.transcript.json
./scripts/render_variants_ffmpeg.sh inbox/clip.mp4 outputs/
python3 scripts/qa_score.py --input inbox/clip.mp4 --output logs/clip.qa.json
```

## Notes
- `transcribe_whisper.py` is a stub with a TODO for real Whisper integration.
- Rendering uses ffmpeg commands for 9:16, 1:1, and 16:9 outputs.
