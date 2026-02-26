# Wedding Site PM — Consolidated Product + Roadmap Context

Updated: 2026-02-26 (PT)
Owner: Eric
Channel: `#wedding-site-pm`

## 1) Mission
Ship a calm, accessible, execution-first wedding website product quickly, then harden and expand.
PM lane enforces proof-based execution, cross-lane alignment (frontend/backend), and blocker visibility.

## 2) Product Direction (Locked)
- UX posture:
  - Accessible by default (WCAG AA, keyboard-first, visible focus states)
  - Low-stimulation, calm interface
  - Fast first success (publishable site in minutes)
  - Progressive power (simple first, advanced controls optional)
- Architecture posture:
  - Section-based content model (Hero, Story, Schedule, RSVP, Travel, Gallery, FAQ, Registry, Footer)
  - Templates define structure + section variants
  - Palettes/tokens create visual variety at scale
- Onboarding decision:
  - Path A: quick intake (auto-populate sections)
  - Path B: skip intake and edit manually
- URL decision:
  - Hosted custom slug
  - Optional custom domain connection

## 3) Product Canon (Consolidated Feature Scope)
Core clusters to track in planning and delivery:
- Site builder + template library + live preview
- Hosting + free tier + custom slug + custom domain
- Theme system: prebuilt palettes + full customization
- RSVP + guest controls + meal/plus-one + reminders + export
- Guest data management + segmentation + event privacy controls
- Content modules: FAQ, travel/accommodations, registry/cash funds
- Messaging: SMS broadcast + 2-way replies + in-app messaging
- Media: photo/video collection, no-app upload, QR upload, pass-the-camera, slideshow
- Collaboration: admin collaborators + granular permissions
- Engagement: polls/quizzes + Spotify voting + time-capsule mechanics
- Analytics/support/export + retention/storage transparency + white-label

## 4) Differentiator Priorities
Current emphasized differentiators:
1. Digital Time Capsule / Vault
2. Guest Time-Capsule Submissions
3. Anniversary Loop System
4. Pass-the-Camera Mode
5. Spotify Song Voting + Approved Sync

## 5) Roadmap Model (Execution Order)
### Phase 1 — MVP ship fast
- Launch core builder flow + publish path + key wedding essentials
- Keep scope tight and outcome-focused

### Phase 2 — Audit + hardening
- Code audit/refactor pass
- Integration verification (frontend ↔ backend contracts)
- Release hardening (validation, security headers, rate limits, logging/monitoring)
- Rollback/backup plan
- Final regression + go/no-go gate

### Phase 3 — Full feature expansion
- Execute remaining canonical feature backlog
- Add future differentiator expansions

## 6) Pricing / GTM Doctrine (Saved)
- Principle: one-time start fee orientation; avoid recurring platform-fee surprises.
- Any third-party pass-through costs (SMS/payment rails/domain) must be transparent before use.
- Positioning wedge: trust + clarity on total cost; no hidden fee behavior.

## 7) PM Operating Contract (Mandatory)
### Proof-based updates only
Every status update must include:
- `commit: <short hash>`
- `files: <changed paths>`
- `verify: <lint/test/build output>`
- `preview: <url OR blocker:+ETA>`

### Status structure
- Always split status by **Frontend** and **Backend**.
- Do not mark **DONE** until proof gates are met.
- If proof gates are not met, label **IN FLIGHT**.

### Blocker escalation
- **S1**: security/credentials/data risk (immediate)
- **S2**: hard blocker >30m
- **S3**: dependency wait (batch)

### Default response shape
1. objective
2. latest proof state FE/BE
3. blockers + owner + ETA
4. next 1–3 concrete actions

## 8) Delivery Reality / Evidence Rules
- Treat real artifacts as truth: local commits, verify output, deploy proof.
- Recent operating reality has often been local commits + Vercel deploys.
- Do not rely on assumptions or channel chatter; require evidence.

## 9) Visual System Context (current palette direction)
Core palette tokens currently referenced:
- Primary: `#7A8F73`
- Hover: `#667B60`
- Soft brand: `#E8EFE5`
- Background: `#FCFBF8`
- Surface: `#F4F1EB`
- Text primary: `#26231F`
- Accent warm: `#C97B5B`
- Accent gold: `#C6A66A`
- Accent plum: `#6F5D7E`

## 10) Source-of-Truth Files
Primary product context:
- `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/wedding-site-context-master.md`
- `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/consolidated-features-list.md`
- `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/roadmap-notes.md`
- `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/figma-board-starter.md`
- `/Users/ericsysclaw/.openclaw/workspace/discord-general/data/site-palette-v1.json`

Market/pricing research context:
- `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/competitor-pricing-dataset.md`
- `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site-chat/competitive-feature-cost-teardown.md`

Historic PM process context:
- `/Users/ericsysclaw/.openclaw/workspace/discord-project-manager/memory/2026-02-10.md`
- `/Users/ericsysclaw/.openclaw/workspace/discord-project-manager/memory/2026-02-11.md`
- `/Users/ericsysclaw/.openclaw/workspace/discord-project-manager/memory/2026-02-12.md`

## 11) Full-Stack Technical Context (Operational)
Primary implementation reference appears to be:
- `/Users/ericsysclaw/.openclaw/workspace/discord-wedding-site/wedding-site`

### Frontend stack
- Next.js App Router (`next@16.1.6`)
- React (`react@19.2.3`, `react-dom@19.2.3`)
- TypeScript
- Tailwind CSS v4 + PostCSS
- ESLint (Next config)

### Backend/API stack
- Next.js API routes under `src/app/api/**`
- Shared domain layer under `src/lib/domain/**`
- Contract-first API shapes under `src/contracts/**` (must update contracts with API changes)

### Data/Auth layer
- Supabase-backed auth/session + data model (from architecture docs)
- Key tables mentioned in current architecture docs:
  - `wedding_sites`, `guests`, `registry_items`, `site_rsvps`, `messages`, `itinerary_items`, `builder_media_assets`
- RLS is expected enabled; owner-scoped CRUD + limited public access patterns

### Testing + quality gates
- Vitest test runner
- Typecheck pass (`tsc --noEmit`)
- Verify command (`npm run verify`) is mandatory proof artifact
- Lint + test + build are part of proof/verification discipline

### Build/deploy
- Local dev: `npm run dev`
- Production build: `npm run build`
- Deploy target: Vercel (preview + production)
- Current delivery pattern often uses local commits + Vercel deploy proofs

### Runtime architecture boundaries (important for lane ownership)
- Frontend lane:
  - `src/app/**` (excluding `src/app/api/**`)
  - UX, accessibility, performance, rendering states
- Backend lane:
  - `src/app/api/**`
  - Validation, transforms, domain rules, API behavior
- Shared boundary:
  - `src/contracts/**` requires FE+BE alignment review

### PM enforcement on technical work
- Any API behavior change must include:
  - contract update,
  - verification output,
  - explicit frontend impact note.
- Any schema/data-affecting change must include:
  - migration/compatibility note,
  - rollback note,
  - affected endpoints/components list.

## 12) Channel Behavior for #wedding-site-pm
- Keep updates concise and machine-checkable.
- Prefer explicit unknowns over guessed certainty.
- Ask for decision only when a genuine product/scope tradeoff is required.
- Everything else: execute and report proof.
