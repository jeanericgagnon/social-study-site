#!/bin/zsh
set -euo pipefail
cd /Users/ericsysclaw/.openclaw/workspace
/usr/bin/python3 ops/docsystem/build_doc_index.py
/usr/bin/python3 ops/docsystem/digest_docs.py
/opt/homebrew/bin/openclaw system event --mode now --text "Docs daily digest updated: docs/40-generated/daily-digest.md" >/dev/null 2>&1 || true
