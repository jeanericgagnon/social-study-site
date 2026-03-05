#!/usr/bin/env python3
import json,re,csv
from pathlib import Path

base=Path('.')
videos=json.loads((base/'openclaw-videos.json').read_text())
norm=base/'normalized'; chunks=base/'chunks'; trans=base/'transcripts'

TOPICS={
 'setup-install':['install','setup','set up','getting started','beginner','local'],
 'automation-agents':['agent','autonomous','automation','workflow','task','orchestr'],
 'integrations':['mcp','api','notion','gmail','discord','slack','whatsapp','telegram','github'],
 'memory-context':['memory','context','knowledge','recall','history'],
 'voice-media':['voice','tts','audio','whisper','transcript','video'],
 'deployment-hosting':['vps','docker','deploy','vercel','cloud','server','self-host'],
 'security-safety':['security','safe','sandbox','permissions','approval','policy'],
 'use-cases':['use case','real world','example','business','productivity'],
 'pricing-business':['pricing','cost','plan','enterprise','free','paid'],
 'comparison-ecosystem':['vs ','versus','competitor','openai','claude','gemini','copilot']
}

def topic_scores(text):
 t=text.lower(); out={}
 for topic,keys in TOPICS.items():
  c=sum(t.count(k) for k in keys)
  if c>0: out[topic]=c
 return out

def quality_score(txt,chunk_count,has_vtt):
 words=len(re.findall(r"[A-Za-z']+",txt)); uniq=len(set(re.findall(r"[A-Za-z']+",txt.lower())))
 lexical=uniq/max(words,1); s=0
 if has_vtt: s+=35
 s+=min(35, words/120); s+=min(20, chunk_count*0.8); s+=min(10, lexical*40)
 return round(min(100,s),1)

manifest=[]
for v in videos:
 vid=v.get('id');
 if not vid: continue
 norm_path=norm/f'{vid}.txt'; txt=norm_path.read_text(errors='ignore') if norm_path.exists() else ''
 chunk_files=sorted([p.name for p in chunks.glob(f'{vid}.part*.txt')])
 vtt_files=sorted([p.name for p in trans.glob(f'{vid}*.vtt')]); has_vtt=bool(vtt_files)
 scores=topic_scores((v.get('title') or '')+'\n'+txt[:120000])
 topics=[k for k,_ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:6]]
 manifest.append({
  'video_id':vid,'title':v.get('title'),'url':v.get('url'),'channel':v.get('channel'),'duration':v.get('duration'),
  'has_vtt':has_vtt,'vtt_files':vtt_files,
  'normalized_path':str(norm_path) if norm_path.exists() else None,
  'chunk_count':len(chunk_files),'chunk_files':chunk_files,
  'quality_score':quality_score(txt,len(chunk_files),has_vtt) if txt else 0,
  'topics':topics,'topic_scores':scores
 })

summary={
 'total_videos':len(manifest),
 'with_vtt':sum(1 for r in manifest if r['has_vtt']),
 'with_normalized':sum(1 for r in manifest if r['normalized_path']),
 'with_chunks':sum(1 for r in manifest if r['chunk_count']>0),
 'avg_quality_score': round(sum(r['quality_score'] for r in manifest)/max(len(manifest),1),1),
}
(base/'manifest.json').write_text(json.dumps({'summary':summary,'videos':manifest},ensure_ascii=False,indent=2),encoding='utf-8')
with open(base/'manifest.csv','w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=['video_id','title','url','channel','duration','has_vtt','normalized_path','chunk_count','quality_score','topics'])
 w.writeheader()
 for r in manifest:
  w.writerow({'video_id':r['video_id'],'title':r['title'],'url':r['url'],'channel':r['channel'],'duration':r['duration'],'has_vtt':r['has_vtt'],'normalized_path':r['normalized_path'],'chunk_count':r['chunk_count'],'quality_score':r['quality_score'],'topics':'|'.join(r['topics'])})
print(summary)
