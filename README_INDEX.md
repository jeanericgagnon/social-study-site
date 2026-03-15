# README_INDEX.md — Start Here

This is the fast navigation map for the workspace markdown system.

## Top 15 (daily use)

1. `MEMORY.md` — curated long-term memory and operating preferences.
2. `memory/2026-03-15.md` — today’s running log.
3. `memory/2026-03-14.md` — yesterday context.
4. `AGENTS.md` — workspace operating rules.
5. `SOUL.md` — assistant behavior/persona.
6. `USER.md` — who Eric is + communication preferences.
7. `TOOLS.md` — local environment/tool notes.
8. `HEARTBEAT.md` — proactive task checklist (currently mostly empty).
9. `daily-brief.md` — daily briefing notes/output.
10. `weekly-review.md` — weekly summary/review notes.
11. `research-digest.md` — research rollups.
12. `ops/error_watcher.py` *(non-md but important)* — low-cost auto-triage watcher.
13. `ops/com.openclaw.error-watcher.plist` *(non-md but important)* — watcher service definition.
14. `docs/` — product/ops documentation set.
15. `discord-tss-second-brain/AGENTS.md` — lane-specific behavior for TSS Second Brain context.

## Working sets

### Core now
- Root identity/behavior files: `AGENTS.md`, `SOUL.md`, `USER.md`, `TOOLS.md`, `HEARTBEAT.md`, `MEMORY.md`
- Day logs: `memory/YYYY-MM-DD.md`
- Outputs: `daily-brief.md`, `weekly-review.md`, `research-digest.md`

### Reference often
- `docs/`
- `ops/`
- `discord-tss-second-brain/` (only when working in that lane)

### Likely archive/noise zones (do not delete blindly)
- `tmp/`
- `recovery-snapshots/`
- `discord-project-manager/context-archives/`
- old lane folders no longer active

## Proposed cleanup plan (safe, staged)

1. Keep this index updated as the single entry point.
2. Add `docs/active/`, `docs/reference/`, `docs/archive/`.
3. Move only clearly stale markdown from `tmp/` + snapshot/archive folders into `docs/archive/` with folder-preserving paths.
4. Keep all root core files in place.
5. Add weekly digest of changed markdown in Top 15 + `docs/active/` only.

## Decision rule for any markdown file

Ask: “Will we read this in the next 30 days?”
- Yes → `active`
- Maybe → `reference`
- No/legacy/generated → `archive`
