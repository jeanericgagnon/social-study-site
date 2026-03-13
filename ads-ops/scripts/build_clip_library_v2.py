#!/usr/bin/env python3
import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".mpg", ".mpeg", ".avi", ".mkv"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha16(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def sh(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def ffprobe_meta(path: Path) -> dict[str, Any]:
    cmd = [
        "/opt/homebrew/bin/ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    p = sh(cmd)
    if p.returncode != 0:
        return {"probe_ok": False, "probe_error": (p.stderr or "ffprobe failed").strip()}

    try:
        j = json.loads(p.stdout or "{}")
    except Exception:
        return {"probe_ok": False, "probe_error": "invalid ffprobe json"}

    fmt = j.get("format", {}) or {}
    streams = j.get("streams", []) or []
    v = next((s for s in streams if s.get("codec_type") == "video"), {})
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})

    duration = 0.0
    try:
        duration = float(fmt.get("duration") or 0.0)
    except Exception:
        duration = 0.0

    fps = None
    fr = v.get("avg_frame_rate") or v.get("r_frame_rate")
    if fr and isinstance(fr, str) and "/" in fr:
        try:
            n, d = fr.split("/", 1)
            d_val = float(d)
            if d_val != 0:
                fps = round(float(n) / d_val, 3)
        except Exception:
            fps = None

    return {
        "probe_ok": True,
        "duration_s": round(duration, 3),
        "width": v.get("width"),
        "height": v.get("height"),
        "fps": fps,
        "video_codec": v.get("codec_name"),
        "audio_codec": a.get("codec_name"),
        "bitrate": fmt.get("bit_rate"),
    }


@dataclass
class SourceRecord:
    source_uid: str
    source_path: str
    rel_path: str
    ext: str
    size_bytes: int
    mtime_epoch: float
    probe_ok: bool
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    bitrate: str | None = None
    probe_error: str | None = None


def list_sources(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            out.append(p)
    return sorted(out)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def init_spec(args: argparse.Namespace) -> int:
    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not root.exists() or not root.is_dir():
        print(json.dumps({"ok": False, "error": f"root not found: {root}"}))
        return 2

    schema_dir = out_dir / "schemas"
    manifests_dir = out_dir / "manifests"
    logs_dir = out_dir / "logs"
    segments_dir = out_dir / "segments"
    thumbs_dir = out_dir / "thumbs"
    for d in [schema_dir, manifests_dir, logs_dir, segments_dir, thumbs_dir]:
        d.mkdir(parents=True, exist_ok=True)

    durations = [float(x.strip()) for x in args.durations.split(",") if x.strip()]
    spec = {
        "version": "clip-library-v2",
        "created_at": now_iso(),
        "root": str(root),
        "out_dir": str(out_dir),
        "durations": durations,
        "stride_min": float(args.stride_min),
        "stride_max": float(args.stride_max),
        "target_min": int(args.target_min),
        "target_max": int(args.target_max),
        "quality_gates": {
            "enabled": bool(args.enforce_quality_gates),
            "required_probe_ok": True,
            "min_duration_s": min(durations) if durations else 1.5,
            "max_duration_s": 600,
            "allowed_decisions": ["use", "conditional", "reject"],
            "reject_on": ["corrupt", "probe_failed", "too_short", "unsupported_format"],
        },
        "output_standard": {
            "resolution": "1080x1920",
            "fps": 30,
            "pix_fmt": "yuv420p",
            "audio": "aac",
        },
    }

    source_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "clip-library-v2-source",
        "type": "object",
        "required": ["source_uid", "source_path", "rel_path", "size_bytes", "probe_ok"],
        "properties": {
            "source_uid": {"type": "string"},
            "source_path": {"type": "string"},
            "rel_path": {"type": "string"},
            "ext": {"type": "string"},
            "size_bytes": {"type": "integer"},
            "mtime_epoch": {"type": "number"},
            "probe_ok": {"type": "boolean"},
            "duration_s": {"type": ["number", "null"]},
            "width": {"type": ["integer", "null"]},
            "height": {"type": ["integer", "null"]},
            "fps": {"type": ["number", "null"]},
            "video_codec": {"type": ["string", "null"]},
            "audio_codec": {"type": ["string", "null"]},
            "bitrate": {"type": ["string", "null"]},
            "probe_error": {"type": ["string", "null"]},
        },
    }

    segment_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "clip-library-v2-segment",
        "type": "object",
        "required": [
            "segment_uid",
            "source_uid",
            "start_sec",
            "end_sec",
            "duration_sec",
            "clip_path",
            "decision",
            "ad_utility_score",
        ],
        "properties": {
            "segment_uid": {"type": "string"},
            "source_uid": {"type": "string"},
            "start_sec": {"type": "number"},
            "end_sec": {"type": "number"},
            "duration_sec": {"type": "number"},
            "clip_path": {"type": "string"},
            "thumb_path": {"type": ["string", "null"]},
            "decision": {"type": "string", "enum": ["use", "conditional", "reject"]},
            "ad_utility_score": {"type": "number"},
            "quality": {
                "type": "object",
                "properties": {
                    "blur_score": {"type": ["number", "null"]},
                    "shake_score": {"type": ["number", "null"]},
                    "exposure_score": {"type": ["number", "null"]},
                    "hook_open_score": {"type": ["number", "null"]},
                    "text_safe_score": {"type": ["number", "null"]},
                },
            },
            "created_at": {"type": "string"},
            "run_id": {"type": "string"},
        },
    }

    write_json(out_dir / "spec_v2.json", spec)
    write_json(schema_dir / "source.schema.v2.json", source_schema)
    write_json(schema_dir / "segment.schema.v2.json", segment_schema)

    sources = list_sources(root)
    records: list[dict[str, Any]] = []
    probe_ok = 0
    for p in sources:
        st = p.stat()
        rel = str(p.relative_to(root))
        meta = ffprobe_meta(p)
        if meta.get("probe_ok"):
            probe_ok += 1
        source_uid = sha16(f"{rel}:{st.st_size}:{int(st.st_mtime)}:v2")
        rec = SourceRecord(
            source_uid=source_uid,
            source_path=str(p),
            rel_path=rel,
            ext=p.suffix.lower(),
            size_bytes=st.st_size,
            mtime_epoch=st.st_mtime,
            probe_ok=bool(meta.get("probe_ok")),
            duration_s=meta.get("duration_s"),
            width=meta.get("width"),
            height=meta.get("height"),
            fps=meta.get("fps"),
            video_codec=meta.get("video_codec"),
            audio_codec=meta.get("audio_codec"),
            bitrate=meta.get("bitrate"),
            probe_error=meta.get("probe_error"),
        )
        records.append(asdict(rec))

    source_manifest = {
        "version": "clip-library-v2",
        "created_at": now_iso(),
        "root": str(root),
        "count_total": len(records),
        "count_probe_ok": probe_ok,
        "count_probe_fail": len(records) - probe_ok,
        "rows": records,
    }
    write_json(manifests_dir / "sources_manifest_v2.json", source_manifest)

    run_summary = {
        "ok": True,
        "phase": "init-spec",
        "spec": str(out_dir / "spec_v2.json"),
        "source_schema": str(schema_dir / "source.schema.v2.json"),
        "segment_schema": str(schema_dir / "segment.schema.v2.json"),
        "sources_manifest": str(manifests_dir / "sources_manifest_v2.json"),
        "count_total": len(records),
        "count_probe_ok": probe_ok,
        "count_probe_fail": len(records) - probe_ok,
        "quality_gates_enabled": bool(args.enforce_quality_gates),
        "durations": durations,
        "stride_min": float(args.stride_min),
        "stride_max": float(args.stride_max),
        "target_min": int(args.target_min),
        "target_max": int(args.target_max),
        "created_at": now_iso(),
    }
    write_json(logs_dir / "init_spec_run_summary.json", run_summary)
    print(json.dumps(run_summary))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Build clip library v2 assets")
    ap.add_argument("--init-spec", action="store_true", help="Initialize v2 spec/schema/manifests")
    ap.add_argument("--root", required=True, help="Source root with approved videos")
    ap.add_argument("--out-dir", required=True, help="Output root for library_v2")
    ap.add_argument("--durations", default="1.5,2.5,3.5,5.0,7.0")
    ap.add_argument("--stride-min", type=float, default=0.75)
    ap.add_argument("--stride-max", type=float, default=1.5)
    ap.add_argument("--target-min", type=int, default=5000)
    ap.add_argument("--target-max", type=int, default=8000)
    ap.add_argument("--enforce-quality-gates", action="store_true")
    args = ap.parse_args()

    if args.init_spec:
        return init_spec(args)

    print(json.dumps({"ok": False, "error": "Only --init-spec is implemented in this phase"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
