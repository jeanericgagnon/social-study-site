#!/usr/bin/env bash
set -euo pipefail

# Safe wrapper for Playwright scraping tasks.
#
# Default mode = validate only (no scraping).
# To execute, pass --execute and provide explicit approval flag.
#
# Examples:
#   ALLOWLIST="example.com,docs.example.com" \
#   sandbox-runners/playwright-scraper/run-safe.sh "https://example.com/docs"
#
#   ALLOWLIST="example.com" \
#   sandbox-runners/playwright-scraper/run-safe.sh --file urls.txt
#
#   ALLOWLIST="example.com" \
#   sandbox-runners/playwright-scraper/run-safe.sh --execute --approve-live-fetch "https://example.com"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VALIDATOR="$SCRIPT_DIR/validate_targets.py"

EXECUTE=0
APPROVED=0
TARGET_URL=""
URL_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute) EXECUTE=1; shift ;;
    --approve-live-fetch) APPROVED=1; shift ;;
    --file) URL_FILE="${2:-}"; shift 2 ;;
    -h|--help)
      sed -n '1,40p' "$0"
      exit 0
      ;;
    *)
      if [[ -z "$TARGET_URL" ]]; then TARGET_URL="$1"; shift; else echo "Unexpected arg: $1" >&2; exit 2; fi
      ;;
  esac
done

if [[ ! -x "$VALIDATOR" ]]; then
  echo "Missing validator: $VALIDATOR" >&2
  exit 2
fi

if [[ -z "${ALLOWLIST:-}" ]]; then
  echo "Blocked: ALLOWLIST env var required (comma-separated domains)." >&2
  exit 3
fi

if [[ -z "$TARGET_URL" && -z "$URL_FILE" ]]; then
  echo "Usage: ALLOWLIST=domain1,domain2 $0 [--file urls.txt] [--execute --approve-live-fetch] <url>" >&2
  exit 2
fi

# Validate targets first
if [[ -n "$URL_FILE" ]]; then
  "$VALIDATOR" --file "$URL_FILE"
else
  "$VALIDATOR" "$TARGET_URL"
fi

mkdir -p .scrapes
TS="$(date +%Y%m%d-%H%M%S)"
LOG=".scrapes/run-${TS}.log"

echo "[$(date -Is)] validated targets" | tee -a "$LOG"
echo "allowlist=$ALLOWLIST" | tee -a "$LOG"
[[ -n "$TARGET_URL" ]] && echo "target=$TARGET_URL" | tee -a "$LOG"
[[ -n "$URL_FILE" ]] && echo "target_file=$URL_FILE" | tee -a "$LOG"

if [[ "$EXECUTE" -eq 0 ]]; then
  echo "Validation complete. Dry-run only (no network fetch executed)." | tee -a "$LOG"
  echo "To execute a live fetch, rerun with: --execute --approve-live-fetch" | tee -a "$LOG"
  exit 0
fi

if [[ "$APPROVED" -ne 1 ]]; then
  echo "Blocked: --execute requires explicit --approve-live-fetch" >&2
  exit 4
fi

# Execution stub: keeps guardrails while allowing future scraper integration.
OUT=".scrapes/scrape-${TS}.md"
{
  echo "# Safe Scrape Run"
  echo "time: $(date -Is)"
  echo "mode: execute-approved"
  echo "targets: ${TARGET_URL:-$URL_FILE}"
  echo "note: hook your Playwright extraction command here after validation gate"
} > "$OUT"

echo "Execute mode approved. Output scaffold written to: $OUT" | tee -a "$LOG"
