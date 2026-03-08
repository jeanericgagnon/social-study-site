#!/bin/bash
# Get X user profile by username
# Usage: ./lookup.sh <username>

set -euo pipefail

USERNAME_RAW="${1:-}"
USERNAME="${USERNAME_RAW#@}"  # Remove @ if present

if [ -z "$USERNAME" ]; then
    echo "Usage: lookup.sh <username>"
    exit 1
fi

# Basic username validation (X usernames: 1-15 chars, letters/numbers/underscore)
if [[ ! "$USERNAME" =~ ^[A-Za-z0-9_]{1,15}$ ]]; then
    echo "Invalid username. Use letters, numbers, underscore (max 15)."
    exit 1
fi

if [ -z "${X_BEARER_TOKEN:-}" ]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    bash "$SCRIPT_DIR/setup.sh"
    exit 1
fi

API_URL="https://api.x.com/2/users/by/username/${USERNAME}?user.fields=id,name,username,description,public_metrics,verified,created_at,profile_image_url"

# Fail on HTTP errors, keep output quiet, enforce timeout to avoid hangs.
curl --fail --silent --show-error --max-time 20 \
  "$API_URL" \
  -H "Authorization: Bearer ${X_BEARER_TOKEN}" | jq '.'
