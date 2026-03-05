#!/usr/bin/env python3
import json, re, sys
from pathlib import Path

q = ' '.join(sys.argv[1:]).strip().lower()
if not q:
    print('Usage: ask_manifest.py "your question"')
    raise SystemExit(2)

base = Path('.')
idx = base / 'query-index.jsonl'
if not idx.exists():
    print('Missing query-index.jsonl. Run build_query_index.py first.')
    raise SystemExit(2)

terms = [t for t in re.findall(r"[a-z0-9']+", q) if len(t) > 2]

scores = []
for line in idx.read_text(errors='ignore').splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    hay = (r['title'] + ' ' + ' '.join(r.get('topics', [])) + ' ' + r['text'][:4000]).lower()
    s = 0
    for t in terms:
        s += hay.count(t)
    s += r.get('quality_score', 0) / 40.0
    if s > 0:
        scores.append((s, r))

scores.sort(key=lambda x: x[0], reverse=True)

seen = set()
top = []
for s, r in scores:
    k = r['chunk_file']
    if k in seen:
        continue
    seen.add(k)
    top.append((s, r))
    if len(top) >= 12:
        break

for i, (s, r) in enumerate(top, 1):
    snippet = re.sub(r"\s+", ' ', r['text'])[:260]
    print(f"[{i}] score={s:.2f}")
    print(f"title: {r['title']}")
    print(f"url: {r['url']}")
    print(f"chunk: {r['chunk_file']}")
    print(f"topics: {', '.join(r.get('topics', []))}")
    print(f"snippet: {snippet}")
    print('-' * 80)
