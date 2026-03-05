# Discord Voice Bot (Batch 1)

This is the Batch 1 skeleton for live voice streaming:
- Join/leave voice channel
- Basic connection health checks
- Foundation for STT/TTS streaming in later batches

## Commands

- `!voice-join` → join your current voice channel
- `!voice-join <channel name>` → join a named voice channel
- `!voice-status` → check connection state
- `!voice-leave` → disconnect

## Setup

1. Copy env template:

```bash
cp .env.example .env
```

2. Fill `.env`:

- `DISCORD_BOT_TOKEN`
- `DISCORD_GUILD_ID` (optional but recommended)

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
