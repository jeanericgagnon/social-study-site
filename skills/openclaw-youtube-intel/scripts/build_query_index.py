#!/usr/bin/env python3
import json
from pathlib import Path

base=Path('.')
manifest=json.loads((base/'manifest.json').read_text())['videos']
out=base/'query-index.jsonl'
with out.open('w',encoding='utf-8') as f:
  for v in manifest:
    for cf in v.get('chunk_files',[]):
      p=base/'chunks'/cf
      if not p.exists():
        continue
      text=p.read_text(errors='ignore').strip()
      if not text:
        continue
      rec={
        'video_id':v['video_id'],'title':v.get('title'),'url':v.get('url'),
        'chunk_file':str(p),'topics':v.get('topics',[]),'quality_score':v.get('quality_score',0),
        'text':text[:12000]
      }
      f.write(json.dumps(rec,ensure_ascii=False)+'\n')
print(f'wrote {out}')
