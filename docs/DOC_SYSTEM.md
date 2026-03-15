# DOC_SYSTEM.md

## Objective
Build a durable, low-friction documentation system that is:
1. Easy to navigate
2. Lossless by default
3. Agent-friendly for context retrieval

## Core Rules
- **Archive-not-delete**: No markdown is deleted by automation.
- **One entrypoint**: `README_INDEX.md` + `docs/50-index/MASTER_INDEX.md`.
- **Three working layers**:
  - `docs/10-active/` current operational docs
  - `docs/20-reference/` evergreen runbooks/playbooks
  - `docs/30-archive/` historical docs
- **Generated output isolation**: `docs/40-generated/` only.
- **Inbox discipline**: uncategorized docs go to `docs/00-inbox/`.

## Standard Metadata (recommended frontmatter)
```yaml
---
title: <human title>
owner: <person/agent>
status: active|reference|archive|generated
last_reviewed: YYYY-MM-DD
tags: [tag1, tag2]
source: manual|automation
---
```

## Automation
- Daily index build + change digest
- Weekly integrity scan + archive candidates report
- All runs log to `logs/docsystem/`

## Safety
- Migrations produce manifest files in `logs/docsystem/`.
- Restore is possible from git and manifests.
- No destructive `rm` operations in automation scripts.
