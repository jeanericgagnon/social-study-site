#!/usr/bin/env bash
set -euo pipefail

# Safe wrapper for Playwright scraping tasks.
# Usage:
#   ALLOWLIST="example.com,docs.example.com" \
#   sandbox-runners/playwright-scraper/run-safe.sh "https://example.com/docs"

URL="${1:-}"
if [[ -z "$URL" ]]; then
  echo "Usage: ALLOWLIST=domain1,domain2 $0 <url>" >&2
  exit 2
fi

ALLOWLIST="${ALLOWLIST:-}"
if [[ -z "$ALLOWLIST" ]]; then
  echo "Blocked: ALLOWLIST env var required (comma-separated domains)." >&2
  exit 3
fi

python3 - "$URL" "$ALLOWLIST" <<'PY'
import ipaddress, socket, sys
from urllib.parse import urlparse

url = sys.argv[1]
allow = [d.strip().lower() for d in sys.argv[2].split(',') if d.strip()]

p = urlparse(url)
if p.scheme not in ("http", "https"):
    raise SystemExit("Blocked: only http/https URLs are allowed")

host = (p.hostname or "").lower().strip('.')
if not host:
    raise SystemExit("Blocked: invalid host")

if not any(host == d or host.endswith("." + d) for d in allow):
    raise SystemExit(f"Blocked: host '{host}' is not in ALLOWLIST")

# Resolve and block private/local ranges.
try:
    addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
except Exception as e:
    raise SystemExit(f"Blocked: DNS resolution failed: {e}")

for a in addrs:
    ip = ipaddress.ip_address(a)
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast):
        raise SystemExit(f"Blocked: resolved IP {ip} is private/local/reserved")

print("OK")
PY

mkdir -p .scrapes
TS="$(date +%Y%m%d-%H%M%S)"
OUT=".scrapes/scrape-${TS}.md"

# Uses OpenClaw built-in fetch tool equivalent via curl as fallback would violate policy,
# so here we just print the approved target and expected output path.
# This wrapper is primarily a safety gate + run metadata recorder.
echo "Approved target: $URL"
echo "Output path: $OUT"
echo "Next step: run scraper against this URL using Playwright workflow."
