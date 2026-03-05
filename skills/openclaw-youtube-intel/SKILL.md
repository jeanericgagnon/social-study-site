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
- `summary.json` (counts + coverage)

## Analysis usage

For deep analysis, read from `chunks/` and cite video IDs/URLs from `openclaw-videos.csv`.
Prefer chunked files for speed/token efficiency; use `normalized/*.txt` only when needed.
