---
name: openclaw-youtube-intel
description: Build a repeatable YouTube intelligence dataset for a keyword (especially OpenClaw): discover all matching videos, fetch subtitle tracks, normalize transcripts, and generate chunked QA-ready text + index files. Use when asked to do deep YouTube research, transcript mining, trend/use-case analysis, or to answer questions grounded in many videos.
---

# OpenClaw YouTube Intel

Use this skill to run a no-API YouTube transcript pipeline.

## Workflow

1. **Discover matching videos**
2. **Download captions/subtitles for each video**
3. **Normalize VTT → plain text transcript per video**
4. **Chunk transcripts for token-safe Q&A**
5. **Produce index/report files**

## Prerequisites

Install once:

```bash
brew install yt-dlp ffmpeg
```

## Run

```bash
skills/openclaw-youtube-intel/scripts/run_pipeline.sh "OpenClaw"
```

Optional output dir:

```bash
skills/openclaw-youtube-intel/scripts/run_pipeline.sh "OpenClaw" exports/openclaw-youtube
```

## Outputs

- `openclaw-videos.json` / `openclaw-videos.csv` (video index)
- `transcripts/*.vtt` (raw subtitle tracks)
- `normalized/*.txt` (clean per-video transcript)
- `chunks/*.txt` (Q&A-ready chunks)
- `manifest.json` / `manifest.csv` (metadata + quality + multi-topic tags)
- `query-index.jsonl` (chunk-level retrieval index)
- `summary.json` (counts + coverage)

## Query mode

Build and query index:

```bash
python skills/openclaw-youtube-intel/scripts/build_query_index.py
python skills/openclaw-youtube-intel/scripts/ask_index.py "onboarding pain points"
```

For deep analysis, read from `query-index.jsonl`/`chunks/` and cite video URLs.
Prefer chunked files for speed/token efficiency; use `normalized/*.txt` only when needed.
