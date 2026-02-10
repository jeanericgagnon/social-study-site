#!/usr/bin/env bash
set -euo pipefail

DATE="$(date +%F)"
ROOT="/Users/ericsysclaw/Desktop/OpenClaw-Memory-Backups"
DEST="$ROOT/$DATE"

mkdir -p "$DEST"

cp -f /Users/ericsysclaw/.openclaw/workspace/MEMORY.md "$DEST/main_MEMORY.md"
cp -f /Users/ericsysclaw/.openclaw/workspace/memory/*.md "$DEST/" 2>/dev/null || true

cp -f /Users/ericsysclaw/.openclaw/workspace/discord-personal/MEMORY.md "$DEST/discord-personal_MEMORY.md" 2>/dev/null || true
cp -f /Users/ericsysclaw/.openclaw/workspace/discord-social-study/MEMORY.md "$DEST/discord-social-study_MEMORY.md" 2>/dev/null || true
cp -f /Users/ericsysclaw/.openclaw/workspace/discord-wedding-site/MEMORY.md "$DEST/discord-wedding-site_MEMORY.md" 2>/dev/null || true

ls -la "$DEST"
