# Discord Voice Bot (Batch 1)

This is the Batch 1+2 foundation for live voice streaming:
- Join/leave voice channel
- Basic connection health checks
- Live voice receive + chunked Whisper transcription to text channel
- Foundation for OpenClaw routing + TTS streaming in later batches

## Commands

- `!voice-join` → join your current voice channel
- `!voice-join <channel name>` → join a named voice channel
- `!voice-status` → check connection/listen state
- `!voice-listen` → start transcribing voice chunks to current text channel
- `!voice-stop` → stop transcription
- `!voice-leave` → disconnect

## Setup

1. Copy env template:

```bash
cp .env.example .env
```

2. Fill `.env`:

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID` (optional but recommended)
- `WHISPER_BIN` (optional; default `../.venv-whisper/bin/whisper`)
- `WHISPER_MODEL` (optional; default `base`)

3. Install + run:

```bash
npm install
npm run start
```

## Discord bot permissions required

- View Channels
- Send Messages
- Connect
- Speak
- Use Voice Activity (optional)

## Next batches

- Batch 2: audio ingest + Whisper STT
- Batch 3: OpenClaw turn router
- Batch 4: TTS back into call
- Batch 5+: safety/hardening
