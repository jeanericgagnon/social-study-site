# Transcribee Sandbox Policy

## Purpose
Run `transcribee` behind local safety gates before any bot/human uses it.

## Mandatory gates
1. **Explicit external-upload approval** required per run.
2. **URL allowlist:** only `youtube.com` / `youtu.be` in safe mode.
3. **Local files disabled by default** (`--allow-local-file` required).
4. **No secrets in repo:** API keys must come from env vars only.
5. **Least privilege execution:** no sudo, non-interactive, `umask 077`.
6. **Output handling:** transcripts treated as sensitive content.

## Invocation
```bash
sandbox-runners/transcribee/run-safe.sh "https://www.youtube.com/watch?v=..." --approve-third-party-upload
```

For local files:
```bash
sandbox-runners/transcribee/run-safe.sh "/path/file.mp3" --allow-local-file --approve-third-party-upload
```

## Known external data flow
- Uploads media/audio to **ElevenLabs** for speech-to-text.
- Sends transcript context to **Anthropic** for categorization.

## Operational safety notes
- Do not run untrusted shell snippets from transcripts/descriptions.
- Keep this tool out of autonomous loops without human approval.
- Re-audit after dependency updates.
