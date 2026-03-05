#!/usr/bin/env python3
import re
import sys
from pathlib import Path


def clean_vtt(text: str) -> str:
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("WEBVTT") or s.startswith("Kind:") or s.startswith("Language:"):
            continue
        if "-->" in s:
            continue
        if re.fullmatch(r"\d+", s):
            continue
        s = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}><c>", "", s)
        s = re.sub(r"</c>", "", s)
        s = re.sub(r"<[^>]+>", "", s)
        s = re.sub(r"\s+", " ", s).strip()
        if s:
            out.append(s)
    # dedupe adjacent repeats
    ded = []
    for x in out:
        if not ded or ded[-1] != x:
            ded.append(x)
    return "\n".join(ded)


def main():
    in_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("transcripts")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("normalized")
    out_dir.mkdir(parents=True, exist_ok=True)
    grouped = {}
    for p in sorted(in_dir.glob("*.vtt")):
        vid = p.name.split(".")[0]
        grouped.setdefault(vid, []).append(p)

    for vid, files in grouped.items():
        # prefer non-auto if available by filename heuristic
        files = sorted(files, key=lambda f: ("orig" not in f.name and "en." not in f.name, len(f.name)))
        text = clean_vtt(files[0].read_text(errors="ignore"))
        (out_dir / f"{vid}.txt").write_text(text, encoding="utf-8")

    print(f"normalized_videos={len(grouped)}")


if __name__ == "__main__":
    main()
