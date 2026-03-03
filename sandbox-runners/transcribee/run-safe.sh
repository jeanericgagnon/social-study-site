#!/usr/bin/env bash
set -euo pipefail

# Safe wrapper for transcribee skill
# - Validates input
# - Requires explicit opt-in for third-party upload
# - Runs with minimal env

SKILL_DIR="${SKILL_DIR:-$HOME/.openclaw/workspace/.agents/skills/transcribee}"
INPUT="${1:-}"

if [[ -z "$INPUT" ]]; then
  echo "Usage: run-safe.sh <youtube-url|local-media-file> [--allow-local-file] [--approve-third-party-upload]"
  exit 2
fi

ALLOW_LOCAL="false"
APPROVE_UPLOAD="false"
for arg in "$@"; do
  [[ "$arg" == "--allow-local-file" ]] && ALLOW_LOCAL="true"
  [[ "$arg" == "--approve-third-party-upload" ]] && APPROVE_UPLOAD="true"
done

if [[ "$APPROVE_UPLOAD" != "true" ]]; then
  echo "Blocked: missing --approve-third-party-upload"
  echo "Reason: transcribee sends media/transcript content to external APIs (ElevenLabs + Anthropic)."
  exit 3
fi

if [[ "$INPUT" =~ ^https?:// ]]; then
  if [[ ! "$INPUT" =~ ^https?://(www\.)?(youtube\.com|youtu\.be)/ ]]; then
    echo "Blocked: only YouTube URLs are allowed in safe mode."
    exit 4
  fi
else
  if [[ "$ALLOW_LOCAL" != "true" ]]; then
    echo "Blocked: local files require --allow-local-file"
    exit 5
  fi
  if [[ ! -f "$INPUT" ]]; then
    echo "Blocked: local file not found: $INPUT"
    exit 6
  fi
fi

if [[ ! -f "$SKILL_DIR/index.ts" ]]; then
  echo "Blocked: transcribee skill not found at $SKILL_DIR"
  exit 7
fi

if [[ -z "${ELEVEN_LABS_API_KEY:-}" || -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Blocked: ELEVEN_LABS_API_KEY and ANTHROPIC_API_KEY must be set in environment."
  exit 8
fi

export OPENCLAW_SANDBOX_MODE=1
export TRANSCRIBEE_SAFE_MODE=1
umask 077

cd "$SKILL_DIR"
exec pnpm exec tsx index.ts "$INPUT"
