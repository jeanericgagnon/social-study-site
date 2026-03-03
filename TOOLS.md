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

## Mac power scheduling (pmset)

Daily wake was configured to help the 5:30am WhatsApp Daily Brief run reliably.

- View scheduled power events:
  - `pmset -g sched`
- Set daily wake (runs in the Mac’s *current* timezone):
  - `sudo pmset repeat wakeorpoweron MTWRFSU 05:25:00`
- Disable the repeating wake schedule (undo):
  - `sudo pmset repeat cancel`

Notes:
- `pmset repeat` typically requires admin (sudo).
- If the Mac timezone changes (travel), the wake time is interpreted in the *new* local time.

Future plan: consider moving OpenClaw + gateway to an always-on host (e.g., Mac mini).

---

Add whatever helps you do your job. This is your cheat sheet.

---

## Skill sandbox safety notes

### Whisper (OpenAI)
- Safe wrapper: `sandbox-runners/whisper/run-safe.sh`
- Policy doc: `sandbox-runners/whisper/SECURITY-POLICY.md`
- Shared reference file: `~/Desktop/OPENCLAW_TOOL_SAFETY_REFERENCE.md`
