#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Stub Whisper transcription step")
    parser.add_argument("--input", required=True, help="Path to input video/audio")
    parser.add_argument("--output", required=True, help="Path to transcript JSON output")
    parser.add_argument("--model", default="base", help="Whisper model name (placeholder)")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": "stub",
        "input": args.input,
        "model": args.model,
        "text": "",
        "segments": [],
        "todo": "Integrate actual Whisper transcription call."
    }
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"Wrote transcription stub: {output_path}")


if __name__ == "__main__":
    main()
