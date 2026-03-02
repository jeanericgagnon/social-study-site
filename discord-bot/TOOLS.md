# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.

---

## Sandbox runners (local skill isolation)
Path: `/Users/ericsysclaw/.openclaw/workspace/discord-bot/sandbox-runners`

Use this wrapper (loads `.env` and dispatches safely):

```bash
./run-skill.sh playwright-mcp smoke '{"url":"https://example.com"}'
./run-skill.sh automation-workflows run '{"workflowId":"smoke-test"}'
./run-skill.sh agentmail send '{"to":"eric@thesocial.study","subject":"Hello","templateId":"brief-v1"}'
```

Security model:
- localhost ports only (`19081/19082/19083`)
- token auth required
- allowlisted actions + payload checks
- no arbitrary shell fallback
