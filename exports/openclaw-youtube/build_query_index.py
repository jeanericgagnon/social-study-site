#!/usr/bin/env python3
import json
from pathlib import Path

base = Path('.')
manifest = json.loads((base / 'manifest.json').read_text())['videos']

out = base / 'query-index.jsonl'
with out.open('w', encoding='utf-8') as f:
    for v in manifest:
        vid = v['video_id']
        title = v.get('title') or ''
        url = v.get('url') or ''
        topics = v.get('topics') or []
        quality = v.get('quality_score', 0)
        for cf in v.get('chunk_files', []):
            p = base / 'chunks' / cf
            if not p.exists():
                continue
            text = p.read_text(errors='ignore').strip()
            if not text:
                continue
            rec = {
                'video_id': vid,
                'title': title,
                'url': url,
                'chunk_file': str(p),
                'topics': topics,
                'quality_score': quality,
                'text': text[:12000]
            }
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')

print(f'wrote {out}')
