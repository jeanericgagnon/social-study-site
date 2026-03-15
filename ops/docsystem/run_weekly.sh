#!/bin/zsh
set -euo pipefail
cd /Users/ericsysclaw/.openclaw/workspace
/usr/bin/python3 ops/docsystem/build_doc_index.py
/usr/bin/python3 ops/docsystem/verify_docs.py
/opt/homebrew/bin/openclaw system event --mode now --text "Docs weekly verify completed: logs/docsystem/weekly-verify.txt" >/dev/null 2>&1 || true
