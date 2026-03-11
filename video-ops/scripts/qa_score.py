#!/usr/bin/env python3
import argparse
import json
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute placeholder QA score")
    parser.add_argument("--input", required=True, help="Input file used for QA")
    parser.add_argument("--output", required=True, help="Path to QA JSON output")
    args = parser.parse_args()

    seed = abs(hash(Path(args.input).name)) % (10**6)
    rng = random.Random(seed)
    score = round(0.6 + rng.random() * 0.4, 3)

    result = {
        "input": args.input,
        "overall_score": score,
        "checks": {
            "hook_strength": round(max(0.0, score - 0.05), 3),
            "caption_readability": round(max(0.0, score - 0.1), 3),
            "format_compliance": round(min(1.0, score + 0.02), 3)
        },
        "status": "pass" if score >= 0.7 else "review"
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2))
    print(f"Wrote QA score: {output_path}")


if __name__ == "__main__":
    main()
