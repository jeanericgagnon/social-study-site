#!/usr/bin/env python3
import json
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path('/Users/ericsysclaw/.openclaw/workspace')
ARCHIVE_ROOT = ROOT / 'docs' / '30-archive'
GENERATED_ROOT = ROOT / 'docs' / '40-generated'
LOG_DIR = ROOT / 'logs' / 'docsystem'

# Conservative one-pass sources: known archive/noise zones only
ARCHIVE_SOURCES = [
    ROOT / 'tmp',
    ROOT / 'recovery-snapshots',
    ROOT / 'discord-project-manager' / 'context-archives',
]

GENERATED_SOURCES = [
    ROOT / 'exports',
]


def gather_markdown(base: Path):
    if not base.exists():
        return []
    return [p for p in base.rglob('*.md') if p.is_file()]


def move_files(files, destination_root, scope_name, manifest):
    moved = 0
    for src in files:
        rel = src.relative_to(ROOT)
        dst = destination_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            continue
        shutil.move(str(src), str(dst))
        manifest.append({'scope': scope_name, 'from': rel.as_posix(), 'to': dst.relative_to(ROOT).as_posix()})
        moved += 1
    return moved


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    archive_dest = ARCHIVE_ROOT / ts
    gen_dest = GENERATED_ROOT / ts

    manifest = []
    archive_count = 0
    for src in ARCHIVE_SOURCES:
        files = gather_markdown(src)
        archive_count += move_files(files, archive_dest, 'archive', manifest)

    generated_count = 0
    for src in GENERATED_SOURCES:
        files = gather_markdown(src)
        generated_count += move_files(files, gen_dest, 'generated', manifest)

    report = {
        'timestamp': ts,
        'archive_moved': archive_count,
        'generated_moved': generated_count,
        'total_moved': archive_count + generated_count,
        'entries': manifest,
    }
    out = LOG_DIR / f'migration-{ts}.json'
    out.write_text(json.dumps(report, indent=2))
    print(f'Moved {report["total_moved"]} markdown files. Manifest: {out}')


if __name__ == '__main__':
    main()
