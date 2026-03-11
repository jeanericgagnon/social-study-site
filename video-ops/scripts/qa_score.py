#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List


def run(cmd: List[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return p.stdout


def ffprobe_duration(input_file: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        out = run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(input_file)
        ]).strip()
        return float(out)
    except Exception:
        return None


def ffmpeg_loudness(input_file: Path) -> float | None:
    if not shutil.which("ffmpeg"):
        return None
    try:
        p = subprocess.run([
            "ffmpeg", "-hide_banner", "-i", str(input_file), "-af", "volumedetect", "-f", "null", "-"
        ], capture_output=True, text=True)
        text = p.stderr
        for line in text.splitlines():
            if "mean_volume:" in line:
                val = line.split("mean_volume:", 1)[1].split(" dB", 1)[0].strip()
                return float(val)
    except Exception:
        return None
    return None


def silence_ratio(input_file: Path, duration: float | None) -> float | None:
    if not shutil.which("ffmpeg") or not duration or duration <= 0:
        return None
    try:
        p = subprocess.run([
            "ffmpeg", "-hide_banner", "-i", str(input_file),
            "-af", "silencedetect=noise=-35dB:d=0.35", "-f", "null", "-"
        ], capture_output=True, text=True)
        sil_start = None
        total_silence = 0.0
        for line in p.stderr.splitlines():
            line = line.strip()
            if "silence_start:" in line:
                sil_start = float(line.rsplit("silence_start:", 1)[1].strip())
            elif "silence_end:" in line and sil_start is not None:
                part = line.rsplit("silence_end:", 1)[1].split("|", 1)[0].strip()
                sil_end = float(part)
                total_silence += max(0.0, sil_end - sil_start)
                sil_start = None
        if sil_start is not None:
            total_silence += max(0.0, duration - sil_start)
        return min(1.0, max(0.0, total_silence / duration))
    except Exception:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Practical QA scoring for rendered video")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--srt", default=None, help="Optional subtitle file path")
    parser.add_argument("--min-duration", type=float, default=10.0)
    parser.add_argument("--max-duration", type=float, default=90.0)
    parser.add_argument("--target-loudness", type=float, default=-16.0)
    parser.add_argument("--max-silence-ratio", type=float, default=0.35)
    args = parser.parse_args()

    input_file = Path(args.input)
    out_file = Path(args.output)
    srt_file = Path(args.srt) if args.srt else input_file.with_suffix(".srt")

    reasons: List[str] = []
    score = 100

    duration = ffprobe_duration(input_file)
    if duration is None:
        reasons.append("Could not measure duration (ffprobe unavailable or failed)")
        score -= 10
    else:
        if duration < args.min_duration:
            reasons.append(f"Duration too short: {duration:.2f}s < {args.min_duration:.2f}s")
            score -= 25
        elif duration > args.max_duration:
            reasons.append(f"Duration too long: {duration:.2f}s > {args.max_duration:.2f}s")
            score -= 20
        else:
            reasons.append(f"Duration OK: {duration:.2f}s")

    mean_vol = ffmpeg_loudness(input_file)
    if mean_vol is None:
        reasons.append("Could not measure average loudness")
        score -= 10
    else:
        delta = abs(mean_vol - args.target_loudness)
        if delta <= 3:
            reasons.append(f"Loudness OK: {mean_vol:.1f} dB")
        elif delta <= 6:
            reasons.append(f"Loudness acceptable but off target: {mean_vol:.1f} dB")
            score -= 8
        else:
            reasons.append(f"Loudness poor: {mean_vol:.1f} dB (target {args.target_loudness:.1f} dB)")
            score -= 18

    sil_ratio = silence_ratio(input_file, duration)
    if sil_ratio is None:
        reasons.append("Could not estimate silence ratio")
        score -= 5
    else:
        if sil_ratio > args.max_silence_ratio:
            reasons.append(f"High silence ratio: {sil_ratio:.2%}")
            score -= 18
        else:
            reasons.append(f"Silence ratio OK: {sil_ratio:.2%}")

    has_subs = srt_file.exists() and srt_file.stat().st_size > 0
    if has_subs:
        reasons.append(f"Subtitles present: {srt_file}")
    else:
        reasons.append("No subtitles present")
        score -= 20

    score = max(0, min(100, score))

    result: Dict[str, Any] = {
        "input": str(input_file),
        "score": score,
        "reasons": reasons,
        "metrics": {
            "duration_seconds": duration,
            "mean_volume_db": mean_vol,
            "silence_ratio": sil_ratio,
            "subtitle_present": has_subs,
            "subtitle_path": str(srt_file),
        },
        "status": "pass" if score >= 70 else "review",
    }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
