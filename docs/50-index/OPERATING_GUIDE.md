# OPERATING_GUIDE.md

## How to use this doc system

1. Start with `README_INDEX.md`
2. Then open `docs/50-index/MASTER_INDEX.md`
3. Work from `docs/10-active/` first
4. Use `docs/20-reference/` for evergreen playbooks
5. Pull history from `docs/30-archive/`

## Automation schedules
- Daily (18:10 local): rebuild index + daily digest
- Weekly (Sunday 18:20 local): index + integrity verify

## Generated outputs
- Daily digest: `docs/40-generated/daily-digest.md`
- Weekly verify: `logs/docsystem/weekly-verify.txt`
- Migration manifests: `logs/docsystem/migration-*.json`

## Restore / rollback
- Use git history for workspace-level restore
- Use migration manifests to reverse specific moves

## Guardrails
- No destructive deletion in automation
- Archive-not-delete policy is default
