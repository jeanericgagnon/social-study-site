#!/usr/bin/env python3
import json,re,sys
from pathlib import Path
q=' '.join(sys.argv[1:]).strip().lower()
if not q:
  print('Usage: ask_index.py "query"'); raise SystemExit(2)
base=Path('.')
idx=base/'query-index.jsonl'
if not idx.exists():
  print('Missing query-index.jsonl'); raise SystemExit(2)
terms=[t for t in re.findall(r"[a-z0-9']+",q) if len(t)>2]
sc=[]
for line in idx.read_text(errors='ignore').splitlines():
  if not line.strip(): continue
  r=json.loads(line)
  hay=(r.get('title','')+' '+' '.join(r.get('topics',[]))+' '+r.get('text','')[:4000]).lower()
  s=sum(hay.count(t) for t in terms)+r.get('quality_score',0)/40
  if s>0: sc.append((s,r))
sc.sort(key=lambda x:x[0], reverse=True)
seen=set(); top=[]
for s,r in sc:
  k=r['chunk_file']
  if k in seen: continue
  seen.add(k); top.append((s,r))
  if len(top)>=12: break
for i,(s,r) in enumerate(top,1):
  snip=re.sub(r"\s+",' ',r['text'])[:240]
  print(f"[{i}] {s:.2f} | {r['title']}\n{r['url']}\n{r['chunk_file']}\n{snip}\n")
