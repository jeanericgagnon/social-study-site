#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def format_ts(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    rem = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{rem:03d}"


def write_srt(segments: List[Dict[str, Any]], srt_path: Path) -> None:
    lines: List[str] = []
    for i, seg in enumerate(segments, start=1):
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start + 2.0))
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        lines.extend([str(i), f"{format_ts(start)} --> {format_ts(end)}", text, ""])
    srt_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def parse_local_whisper_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    # openai-whisper CLI outputs segments in .json for --output_format json
    segments = payload.get("segments", []) or []
    text = payload.get("text", "")
    if not text and segments:
        text = " ".join(str(s.get("text", "")).strip() for s in segments).strip()
    return {"text": text, "segments": segments, "raw": payload}


def transcribe_local_whisper(input_path: Path, base_out: Path, model: str, language: str | None) -> Dict[str, Any]:
    whisper_bin = shutil.which("whisper")
    if not whisper_bin:
        raise RuntimeError("local whisper CLI not found")

    out_dir = base_out.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        whisper_bin,
        str(input_path),
        "--model",
        model,
        "--output_dir",
        str(out_dir),
        "--output_format",
        "all",
        "--verbose",
        "False",
    ]
    if language:
        cmd.extend(["--language", language])

    subprocess.run(cmd, check=True)

    stem = input_path.stem
    json_path = out_dir / f"{stem}.json"
    srt_path = out_dir / f"{stem}.srt"
    if not json_path.exists():
        raise RuntimeError(f"Whisper completed but JSON output missing: {json_path}")

    parsed = parse_local_whisper_json(json_path)
    # normalize/rename output to requested base_out paths
    target_json = Path(str(base_out) + ".json")
    target_srt = Path(str(base_out) + ".srt")
    target_json.write_text(json.dumps({
        "engine": "local_whisper_cli",
        "model": model,
        "input": str(input_path),
        "text": parsed["text"],
        "segments": parsed["segments"],
    }, indent=2), encoding="utf-8")

    if srt_path.exists():
        target_srt.write_text(srt_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        write_srt(parsed["segments"], target_srt)

    return {"json": str(target_json), "srt": str(target_srt), "engine": "local_whisper_cli"}


def transcribe_openai(input_path: Path, base_out: Path, model: str) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    cmd = [
        "curl",
        "-sS",
        "https://api.openai.com/v1/audio/transcriptions",
        "-H",
        f"Authorization: Bearer {api_key}",
        "-F",
        f"file=@{input_path}",
        "-F",
        "model=whisper-1",
        "-F",
        "response_format=verbose_json",
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    payload = json.loads(proc.stdout)
    segments = payload.get("segments", []) or []
    text = payload.get("text", "")

    target_json = Path(str(base_out) + ".json")
    target_srt = Path(str(base_out) + ".srt")
    target_json.write_text(json.dumps({
        "engine": "openai_whisper_api",
        "model": "whisper-1",
        "input": str(input_path),
        "text": text,
        "segments": segments,
        "raw": payload,
    }, indent=2), encoding="utf-8")

    if segments:
        write_srt(segments, target_srt)
    else:
        target_srt.write_text("", encoding="utf-8")

    return {"json": str(target_json), "srt": str(target_srt), "engine": "openai_whisper_api"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe media with Whisper (local-first)")
    parser.add_argument("--input", required=True, help="Path to input video/audio")
    parser.add_argument("--output-base", required=True, help="Base output path without extension")
    parser.add_argument("--model", default="base", help="Local whisper model name")
    parser.add_argument("--language", default=None, help="Optional language code")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}", file=sys.stderr)
        sys.exit(2)

    base_out = Path(args.output_base).resolve()
    base_out.parent.mkdir(parents=True, exist_ok=True)

    whisper_available = shutil.which("whisper") is not None
    openai_key = bool(os.getenv("OPENAI_API_KEY"))

    try:
        if whisper_available:
            result = transcribe_local_whisper(input_path, base_out, args.model, args.language)
        elif openai_key:
            result = transcribe_openai(input_path, base_out, args.model)
        else:
            raise RuntimeError(
                "No transcription backend available: install local `whisper` CLI (preferred) "
                "or set OPENAI_API_KEY for API fallback."
            )
    except subprocess.CalledProcessError as e:
        print(f"ERROR: transcription command failed: {e}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(3)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(4)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
