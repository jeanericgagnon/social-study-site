# OpenClaw Tool Safety Reference (for Eric + bots)

Updated: 2026-03-03

## Current transcription stack
- ❌ Removed: `transcribee` skill and sandbox
- ✅ Active: `openai-whisper-api` via safe wrapper

## Whisper safe wrapper
- Wrapper: `sandbox-runners/whisper/run-safe.sh`
- Policy: `sandbox-runners/whisper/SECURITY-POLICY.md`
- Output folder (default): `~/Documents/transcripts/whisper`

### Required flags
- `--approve-openai-upload` (mandatory each run)

### Optional flags
- `--allow-local-file` (required for local files)
- `--language en`
- `--json`
- `--out /path/to/output.txt`

## Command examples
```bash
export OPENAI_API_KEY=...

# YouTube URL
sandbox-runners/whisper/run-safe.sh "https://www.youtube.com/watch?v=..." --approve-openai-upload

# Local file
sandbox-runners/whisper/run-safe.sh "/path/audio.mp3" --allow-local-file --approve-openai-upload
```

## Safety behavior
- Blocks without explicit OpenAI upload approval flag.
- URL mode only allows YouTube links.
- Local file mode is disabled by default.
- No keys stored in repo (env only).

## Tooling dependencies
- `yt-dlp` needed for URL mode.
- `curl` needed by OpenAI Whisper script.
