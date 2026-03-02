#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 ]]; then
  echo "Usage: $0 <skill> <action> '<json-payload>'"
  exit 2
fi

SKILL="$1"
ACTION="$2"
PAYLOAD="$3"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

set -a
source .env
set +a

exec python3 dispatch.py --skill "$SKILL" --action "$ACTION" --payload "$PAYLOAD"
