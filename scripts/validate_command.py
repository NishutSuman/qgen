#!/usr/bin/env python3
"""validate_command.py — Phase 0.

Parse the generation command and HARD-STOP if count != sum(difficulty ratio).

Usage:
    python scripts/validate_command.py \
        --count 50 --difficulty "0:8, 0.5:18, 1:24" --notes "..." \
        --id-start 1 --out work/command.json
"""
import argparse
import json
import sys

VALID_LEVELS = {"0", "0.5", "1"}


def parse_difficulty(raw: str) -> dict:
    out = {}
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            sys.exit(f"[FAIL] bad difficulty token '{chunk}' (expected level:count)")
        level, count = (p.strip() for p in chunk.split(":", 1))
        if level not in VALID_LEVELS:
            sys.exit(f"[FAIL] invalid difficulty level '{level}' (allowed: 0, 0.5, 1)")
        try:
            count = int(count)
        except ValueError:
            sys.exit(f"[FAIL] non-integer count '{count}' for level {level}")
        if count < 0:
            sys.exit(f"[FAIL] negative count for level {level}")
        out[level] = out.get(level, 0) + count
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, required=True)
    ap.add_argument("--difficulty", required=True)
    ap.add_argument("--notes", default="")
    ap.add_argument("--id-start", type=int, default=1)
    ap.add_argument("--out", default="work/command.json")
    args = ap.parse_args()

    if args.count <= 0:
        sys.exit("[FAIL] --count must be a positive integer")

    ratio = parse_difficulty(args.difficulty)
    total = sum(ratio.values())
    if total != args.count:
        sys.exit(
            f"[FAIL] difficulty counts sum to {total} but --count is {args.count}. "
            f"Fix the command before proceeding."
        )

    payload = {
        "count": args.count,
        "difficulty_ratio": ratio,
        "notes": args.notes,
        "id_start": args.id_start,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[PASS] command valid: {args.count} questions, ratio {ratio}")
    print(f"[PASS] wrote {args.out}")


if __name__ == "__main__":
    main()
