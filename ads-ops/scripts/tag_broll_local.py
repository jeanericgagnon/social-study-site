#!/usr/bin/env python3
import argparse, json, subprocess
from pathlib import Path


def ffprobe_json(path: Path):
    out = subprocess.check_output([
        'ffprobe', '-v', 'error', '-print_format', 'json', '-show_streams', '-show_format', str(path)
    ])
    return json.loads(out)


def scene_cut_count(path: Path, threshold: float = 0.35) -> int:
    cmd = ['ffmpeg', '-hide_banner', '-i', str(path), '-filter:v', f"select='gt(scene,{threshold})',showinfo", '-f', 'null', '-']
    p = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    return p.stderr.count('Parsed_showinfo')


def main():
    ap = argparse.ArgumentParser(description='Local structural tagger for ad b-roll candidates')
    ap.add_argument('--media-dir', required=True)
    ap.add_argument('--out-json', required=True)
    ap.add_argument('--max-duration-sec', type=float, default=300.0)
    ap.add_argument('--scene-threshold', type=float, default=0.35, help='ffmpeg scene detection threshold; higher = fewer detected cuts')
    ap.add_argument('--limit', type=int, default=0, help='0 = no limit')
    args = ap.parse_args()

    files = sorted(Path(args.media_dir).glob('*.mp4'))
    if args.limit and args.limit > 0:
        files = files[:args.limit]

    rows = []
    skipped_long = 0

    for f in files:
        meta = ffprobe_json(f)
        streams = [s for s in meta.get('streams', []) if s.get('codec_type') == 'video']
        if not streams:
            continue
        v = streams[0]
        dur = float(meta.get('format', {}).get('duration', 0) or 0)
        if dur > args.max_duration_sec:
            rows.append({
                'media_id': f.stem,
                'path': str(f),
                'duration_s': round(dur, 2),
                'skip': True,
                'skip_reason': 'long_form_over_5min'
            })
            skipped_long += 1
            continue

        cuts = scene_cut_count(f, threshold=args.scene_threshold)
        cpm = cuts / (dur / 60.0) if dur > 0 else 0.0

        # Heuristic labels for ad b-roll/pan workflows
        likely_pan_broll = (dur >= 8 and dur <= 90 and cpm <= 24)
        pacing = 'low' if cpm < 25 else ('medium' if cpm <= 70 else 'high')

        rows.append({
            'media_id': f.stem,
            'path': str(f),
            'duration_s': round(dur, 2),
            'resolution': f"{v.get('width')}x{v.get('height')}",
            'scene_cuts': int(cuts),
            'cuts_per_min': round(cpm, 2),
            'pacing': pacing,
            'likely_pan_broll': likely_pan_broll,
            'skip': False,
            'skip_reason': None
        })

    out = {
        'total_files': len(files),
        'processed': sum(1 for r in rows if not r.get('skip')),
        'skipped_long': skipped_long,
        'pan_broll_candidates': sum(1 for r in rows if r.get('likely_pan_broll')),
        'rows': rows,
    }

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps({
        'total_files': out['total_files'],
        'processed': out['processed'],
        'skipped_long': out['skipped_long'],
        'pan_broll_candidates': out['pan_broll_candidates']
    }, indent=2))
    print(f'wrote {out_path}')


if __name__ == '__main__':
    main()
