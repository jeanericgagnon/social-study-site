#!/usr/bin/env python3
import argparse
import json
import random
import subprocess
from pathlib import Path
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def sh(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def load_rows(index_json: Path):
    j = json.loads(index_json.read_text())
    return j.get('rows', [])


def pick_variants(rows, n, seed=42):
    rnd = random.Random(seed)
    hooks = [r for r in rows if 'hook' in (r.get('role_bucket') or '')]
    bodies = [r for r in rows if 'body' in (r.get('role_bucket') or '')]
    ctas = [r for r in rows if 'cta' in (r.get('role_bucket') or '')]
    broll = [r for r in rows if 'broll' in (r.get('role_bucket') or '')]

    if not hooks or not bodies:
        raise RuntimeError('Not enough hook/body clips to build variants')

    out = []
    for i in range(1, n + 1):
        h = rnd.choice(hooks)
        b = rnd.choice(bodies)
        c = rnd.choice(ctas) if ctas else rnd.choice(broll or bodies)

        # encourage diversity in source usage
        tries = 0
        while len({h['source_uid'], b['source_uid'], c['source_uid']}) < 2 and tries < 20:
            b = rnd.choice(bodies)
            c = rnd.choice(ctas) if ctas else rnd.choice(broll or bodies)
            tries += 1

        clips = [h, b, c]
        dur = round(sum(float(x.get('duration_sec', 0)) for x in clips), 3)
        score = round(sum(float(x.get('ad_utility_score', 0)) for x in clips) / len(clips), 2)

        out.append({
            'variant_id': f'vb1_{i:04d}',
            'created_at': now_iso(),
            'clips': [
                {'segment_uid': x['segment_uid'], 'clip_path': x['clip_path'], 'source_uid': x['source_uid'], 'role': role}
                for x, role in zip(clips, ['hook', 'body', 'cta'])
            ],
            'duration_total_s': dur,
            'avg_clip_score': score,
            'tags': ['variant-batch-v1', 'hook-body-cta']
        })

    return out


def render_variant(variant, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = variant['variant_id']
    out_mp4 = out_dir / f'{vid}.mp4'

    # build ffmpeg command with concat filter
    inputs = []
    filter_parts = []
    concat_in = ''
    for idx, c in enumerate(variant['clips']):
        p = c['clip_path']
        inputs.extend(['-i', p])
        filter_parts.append(f'[{idx}:v:0]scale=1080:1920,setsar=1[v{idx}]')
        filter_parts.append(f'[{idx}:a:0]anull[a{idx}]')
        concat_in += f'[v{idx}][a{idx}]'

    filter_complex = ';'.join(filter_parts + [f'{concat_in}concat=n={len(variant["clips"])}:v=1:a=1[v][a]'])

    cmd = [
        '/opt/homebrew/bin/ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '[v]', '-map', '[a]',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '22',
        '-c:a', 'aac', '-b:a', '128k',
        str(out_mp4)
    ]
    p = sh(cmd)
    return p.returncode == 0 and out_mp4.exists(), (p.stderr or '').strip()[:300]


def main():
    ap = argparse.ArgumentParser(description='Build and optionally render variant batch from kept index')
    ap.add_argument('--index-json', required=True)
    ap.add_argument('--out-dir', required=True)
    ap.add_argument('--count', type=int, default=100)
    ap.add_argument('--render', action='store_true')
    ap.add_argument('--render-count', type=int, default=30)
    ap.add_argument('--seed', type=int, default=42)
    args = ap.parse_args()

    index_json = Path(args.index_json).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(index_json)
    variants = pick_variants(rows, args.count, args.seed)

    plan_json = out_dir / 'variant_batch_v1_plan.json'
    plan_jsonl = out_dir / 'variant_batch_v1_plan.jsonl'
    plan_json.write_text(json.dumps({'created_at': now_iso(), 'count': len(variants), 'rows': variants}, indent=2) + '\n')
    with plan_jsonl.open('w') as f:
        for v in variants:
            f.write(json.dumps(v) + '\n')

    rendered = 0
    failed = 0
    failures = []
    if args.render:
        render_dir = out_dir / 'renders'
        for v in variants[: args.render_count]:
            ok, err = render_variant(v, render_dir)
            if ok:
                rendered += 1
            else:
                failed += 1
                failures.append({'variant_id': v['variant_id'], 'error': err})

    summary = {
        'ok': True,
        'created_at': now_iso(),
        'index': str(index_json),
        'plan_json': str(plan_json),
        'plan_jsonl': str(plan_jsonl),
        'variant_count': len(variants),
        'render_enabled': bool(args.render),
        'render_count_requested': int(args.render_count),
        'rendered': rendered,
        'failed': failed,
        'failures_sample': failures[:10],
    }
    (out_dir / 'variant_batch_v1_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
