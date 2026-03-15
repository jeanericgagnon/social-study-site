#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
from datetime import datetime

ROOT = Path('/Users/ericsysclaw/.openclaw/workspace')
INDEX_DIR = ROOT / 'docs' / '50-index'
EXCLUDE_PARTS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__'}


def is_md(p: Path) -> bool:
    return p.suffix.lower() == '.md' and not any(part in EXCLUDE_PARTS for part in p.parts)


def main():
    mds = [p for p in ROOT.rglob('*.md') if is_md(p)]
    mds.sort()
    by_top = Counter()
    for p in mds:
        rel = p.relative_to(ROOT)
        by_top[rel.parts[0] if len(rel.parts) > 1 else '(root)'] += 1

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    out = INDEX_DIR / 'MASTER_INDEX.md'
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')

    lines = [
        '# MASTER_INDEX.md',
        '',
        f'_Generated: {ts}_',
        '',
        f'- Total markdown files: **{len(mds)}**',
        '',
        '## By top-level folder',
        ''
    ]
    for k, v in by_top.most_common():
        lines.append(f'- `{k}`: {v}')

    lines += ['', '## Key docs', '']
    key_docs = [
        'README_INDEX.md', 'MEMORY.md', 'AGENTS.md', 'SOUL.md', 'USER.md', 'TOOLS.md', 'HEARTBEAT.md',
        'docs/DOC_SYSTEM.md'
    ]
    for kd in key_docs:
        p = ROOT / kd
        if p.exists():
            lines.append(f'- `{kd}`')

    lines += ['', '## Full markdown list', '']
    for p in mds:
        lines.append(f'- `{p.relative_to(ROOT).as_posix()}`')

    out.write_text('\n'.join(lines) + '\n')
    print(f'Wrote {out}')


if __name__ == '__main__':
    main()
