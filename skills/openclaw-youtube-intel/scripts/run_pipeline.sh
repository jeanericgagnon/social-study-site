#!/usr/bin/env bash
set -euo pipefail

QUERY="${1:-OpenClaw}"
OUTDIR="${2:-exports/openclaw-youtube}"

mkdir -p "$OUTDIR" "$OUTDIR/transcripts" "$OUTDIR/normalized" "$OUTDIR/chunks"

pushd "$OUTDIR" >/dev/null

echo "[1/5] Discover videos for query: $QUERY"
yt-dlp "ytsearchall:${QUERY}" --flat-playlist --dump-json > raw-search.jsonl

python3 - <<'PY'
import json,csv
from pathlib import Path
q=(Path('raw-search.jsonl').read_text(errors='ignore').splitlines())
rows=[]
for line in q:
    if not line.strip():
        continue
    try:d=json.loads(line)
    except:continue
    title=(d.get('title') or '')
    if 'openclaw' in title.lower():
        vid=d.get('id')
        if not vid: continue
        rows.append({
            'id':vid,
            'title':title,
            'url':f'https://www.youtube.com/watch?v={vid}',
            'channel':d.get('channel') or d.get('uploader') or '',
            'duration':d.get('duration')
        })
seen=set();ded=[]
for r in rows:
    if r['id'] in seen: continue
    seen.add(r['id']); ded.append(r)
Path('openclaw-videos.json').write_text(json.dumps(ded,ensure_ascii=False,indent=2),encoding='utf-8')
with open('openclaw-videos.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=['id','title','url','channel','duration'])
    w.writeheader(); w.writerows(ded)
print(f'videos={len(ded)}')
PY

echo "[2/5] Download subtitles"
python3 - <<'PY'
import json,subprocess
from pathlib import Path
videos=json.loads(Path('openclaw-videos.json').read_text())
Path('transcripts').mkdir(exist_ok=True)
for v in videos:
    vid=v['id']; url=v['url']
    cmd=['yt-dlp','--skip-download','--write-auto-subs','--write-subs','--sub-langs','en.*','--sub-format','vtt','-o','transcripts/%(id)s.%(ext)s',url]
    subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print(f'processed={len(videos)}')
PY

echo "[3/5] Normalize VTT"
python3 ../../skills/openclaw-youtube-intel/scripts/normalize_vtt.py transcripts normalized

echo "[4/5] Chunk transcripts"
python3 ../../skills/openclaw-youtube-intel/scripts/chunk_transcripts.py normalized chunks

echo "[5/7] Build manifest"
python3 ../../skills/openclaw-youtube-intel/scripts/build_manifest.py

echo "[6/7] Build query index"
python3 ../../skills/openclaw-youtube-intel/scripts/build_query_index.py

echo "[7/7] Write summary"
python3 - <<'PY'
import json
from pathlib import Path
summary={
  'videos_indexed': len(json.loads(Path('openclaw-videos.json').read_text())),
  'vtt_files': len(list(Path('transcripts').glob('*.vtt'))),
  'normalized_files': len(list(Path('normalized').glob('*.txt'))),
  'chunk_files': len(list(Path('chunks').glob('*.txt'))),
  'manifest_exists': Path('manifest.json').exists(),
  'query_index_exists': Path('query-index.jsonl').exists()
}
Path('summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(summary)
PY

popd >/dev/null
echo "Done. Output: $OUTDIR"
