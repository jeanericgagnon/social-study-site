# Whisper Sandbox Policy

## Purpose
Safe transcription using OpenAI Whisper API instead of transcribee.

## Mandatory gates
1. Require explicit `--approve-openai-upload` each run.
2. URL mode allowlist: only `youtube.com` / `youtu.be`.
3. Local-file mode off by default (`--allow-local-file` required).
4. `OPENAI_API_KEY` only from environment.
5. Store outputs under `~/Documents/transcripts/whisper`.

## Command
```bash
sandbox-runners/whisper/run-safe.sh "https://www.youtube.com/watch?v=..." --approve-openai-upload
```

## Privacy note
Audio is uploaded to OpenAI transcription API.
