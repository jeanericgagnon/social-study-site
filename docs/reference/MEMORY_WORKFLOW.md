# Memory workflow (local-only)

## Goals
- Keep `MEMORY.md` lightweight and *high signal* (curated).
- Keep a full, append-only archive we can search anytime.

## Where things live
- **Curated long-term memory:** `~/.openclaw/workspace/MEMORY.md`
- **Daily running notes:** `~/.openclaw/workspace/memory/YYYY-MM-DD.md`
- **Daily chat ledger:** `~/.openclaw/workspace/vault/ledger/YYYY-MM-DD.md`
- **Daily chat index (JSONL):** `~/.openclaw/workspace/vault/ledger/YYYY-MM-DD.index.jsonl`
- **Weekly merged index:** `~/.openclaw/workspace/vault/ledger_weekly/YYYY-Www.index.jsonl`
- **Archive scratchpad (raw paste/dumps):** `~/.openclaw/workspace/vault/archive/INBOX.md`

## How to use the archive scratchpad
When you want to dump context without cluttering `MEMORY.md`:
1) Paste it into `vault/archive/INBOX.md` (append at bottom, keep timestamps).
2) Tell Sys what it is (e.g., “old chat export”, “bio notes”, “project history”).
3) Sys will:
   - split it into files under `vault/archive/` (by topic/date)
   - create/update an index file
   - optionally promote the *distilled* pieces into `MEMORY.md`

## Promotion rule (keep MEMORY.md clean)
Only promote items that are:
- durable (still true in 3+ months)
- repeatedly useful
- preferences / decisions / policies / key people / systems

Everything else stays in `vault/`.
