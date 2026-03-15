#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime

ROOT = Path('/Users/ericsysclaw/.openclaw/workspace')
OUT = ROOT / 'logs' / 'docsystem' / 'weekly-verify.txt'


def main():
    total = 0
    empty = []
    giant = []
    for p in ROOT.rglob('*.md'):
        if not p.is_file() or '.git' in p.parts:
            continue
        total += 1
        size = p.stat().st_size
        if size == 0:
            empty.append(p)
        if size > 500_000:
            giant.append((p, size))

    lines = [
        f'Weekly doc verify: {datetime.now().isoformat()}',
        f'Total markdown files: {total}',
        f'Empty markdown files: {len(empty)}',
        f'Large markdown files (>500KB): {len(giant)}',
        '',
    ]
    if empty:
        lines.append('Empty files:')
        lines += [f'- {p.relative_to(ROOT).as_posix()}' for p in empty[:100]]
    if giant:
        lines.append('Large files:')
        lines += [f'- {p.relative_to(ROOT).as_posix()} ({s} bytes)' for p, s in giant[:100]]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text('\n'.join(lines) + '\n')
    print(f'Wrote {OUT}')


if __name__ == '__main__':
    main()
