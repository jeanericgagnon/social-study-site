# Wedding Site PM — Consolidated Context (for #wedding-site-pm)

Updated: 2026-02-26
Owner: Eric

## 1) Mission
Ship a calm, accessible, execution-first wedding website product quickly.
PM lane exists to keep frontend/backend aligned, enforce proof-based progress, surface blockers early, and keep scope disciplined.

## 2) Product Direction (locked)
- UX principles:
  - Accessible by default (WCAG AA, keyboard-first, clear focus states)
  - Low-stimulation, calm UI
  - Fast first success (publishable site in minutes)
  - Progressive power (simple first, advanced optional)
- Architecture:
  - Section-based system (Hero, Story, Schedule, RSVP, Travel, Gallery, FAQ, Registry, Footer)
  - Templates define structure/variant composition
  - Palettes/tokens provide visual variety at scale
- Onboarding:
  - Path A: Quick intake auto-populates sections
  - Path B: Skip + manual section editing
- URL model:
  - Hosted custom slug
  - Optional custom domain connection

## 3) MVP Priorities (current execution order)
1. Audit/stabilize build for errors
2. Add remaining must-have features
3. UX polish

Required passes in this phase:
- Frontend ↔ backend integration verification
- Release hardening (validation, security headers, rate limits, logging/monitoring)
- Rollback/backup plan
- Final go/no-go checklist with full build + regression smoke

## 4) PM Operating Rules (how this lane runs)
- Proof over chatter. Required proof block format:
  - `commit: <short hash>`
  - `files: <changed paths>`
  - `verify: <lint/test/build output>`
  - `preview: <url OR blocker:+ETA>`
- Status labels:
  - Use **IN FLIGHT** until proof gates are met.
  - Do not call DONE early from velocity alone.
- Scope discipline:
  - Core path ships first.
  - Non-critical polish/debt goes to queued cleanup batches.
- Escalation severity:
  - S1: security/credentials/data risk (immediate)
  - S2: hard blocker >30m
  - S3: normal dependency wait (batch)
- Reporting preference (when asked "status"):
  - Split by Frontend / Backend
  - Include: health emoji, last local commit+time, shipped/working on, downtime/uptime, ETA to next proof, ETA to deliverable, efficiency label

## 5) Source of Truth Files
- Product context:
  - `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/wedding-site-context-master.md`
  - `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/consolidated-features-list.md`
  - `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/figma-board-starter.md`
- Visual tokens/palette:
  - `/Users/ericsysclaw/.openclaw/workspace/discord-general/data/site-palette-v1.json`
- PM lane memory snapshots:
  - `/Users/ericsysclaw/.openclaw/workspace/discord-project-manager/memory/2026-02-10.md`
  - `/Users/ericsysclaw/.openclaw/workspace/discord-project-manager/memory/2026-02-11.md`
  - `/Users/ericsysclaw/.openclaw/workspace/discord-project-manager/memory/2026-02-12.md`

## 6) Consolidated Feature Canon (top clusters)
- Core builder + templates + live preview
- Hosting, free tier, custom slug, optional custom domain
- Theme system: prebuilt palettes + full customization
- RSVP + guest management + exports + reminders
- Messaging: SMS + in-app broadcast/replies
- Media: photo/video upload, QR upload, pass-the-camera, slideshow
- Registry + cash fund + fee transparency
- Collaboration + roles/permissions
- Polls/quizzes + visibility rules
- Spotify playlist + voting/approval sync
- Time capsule + anniversary loop + guest contributions
- Analytics + support + white-label options

## 7) Current Known Delivery Reality
- Recent shipping pattern has been local commits + Vercel deploys.
- GitHub auth friction existed on host previously but did not block local+Vercel execution.
- PM should evaluate real artifacts (commits, deploy proofs, verification outputs), not assumptions.

## 8) Suggested Default Behavior in #wedding-site-pm
- On mention or task request:
  1) Acknowledge objective in one line
  2) Return latest Frontend/Backend proof state
  3) Call out blockers + owner + ETA
  4) Propose next 1–3 concrete actions
- Keep messages concise and machine-checkable.
- Prefer evidence and explicit unknowns over confident guesses.
