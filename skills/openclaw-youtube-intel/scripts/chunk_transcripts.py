#!/usr/bin/env python3
import sys
from pathlib import Path

CHARS = 5000
OVERLAP = 500


def chunks(s: str, n: int, overlap: int):
    i = 0
    L = len(s)
    while i < L:
        j = min(L, i + n)
        yield s[i:j]
        if j == L:
            break
        i = max(0, j - overlap)


def main():
    in_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("normalized")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("chunks")
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for p in sorted(in_dir.glob("*.txt")):
        txt = p.read_text(errors="ignore")
        vid = p.stem
        for idx, c in enumerate(chunks(txt, CHARS, OVERLAP), 1):
            (out_dir / f"{vid}.part{idx:03d}.txt").write_text(c, encoding="utf-8")
            total += 1
    print(f"chunk_files={total}")


if __name__ == "__main__":
    main()
