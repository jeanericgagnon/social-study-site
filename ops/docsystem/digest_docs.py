#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path('/Users/ericsysclaw/.openclaw/workspace')
OUT = ROOT / 'docs' / '40-generated' / 'daily-digest.md'
WINDOW_HOURS = 24

PRIORITY_DIRS = [
    ROOT,
    ROOT / 'memory',
    ROOT / 'docs' / '10-active',
    ROOT / 'docs' / '20-reference',
]


def main():
    cutoff = datetime.now().timestamp() - WINDOW_HOURS * 3600
    changed = []
    for p in ROOT.rglob('*.md'):
        if not p.is_file() or '.git' in p.parts:
            continue
        if p.stat().st_mtime >= cutoff:
            changed.append(p)

    changed.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    lines = [
        '# Daily Markdown Digest',
        '',
        f'- Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        f'- Window: last {WINDOW_HOURS} hours',
        f'- Changed markdown files: **{len(changed)}**',
        '',
        '## Recent changes',
        ''
    ]

    for p in changed[:80]:
        rel = p.relative_to(ROOT).as_posix()
        ts = datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
        lines.append(f'- `{rel}` (updated {ts})')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('\n'.join(lines) + '\n')
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
