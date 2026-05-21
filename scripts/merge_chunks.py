#!/usr/bin/env python3
"""merge_chunks.py — Phase 2 merge.

Combine all work/questions_chunk_*.json into a single work/questions.json,
sorted by question_id. Detects missing IDs vs the plan and duplicate writes.

Usage:
    python scripts/merge_chunks.py --plan plan.json \
        --glob "work/questions_chunk_*.json" --out work/questions.json
"""
import argparse
import glob
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--glob", default="work/questions_chunk_*.json")
    ap.add_argument("--out", default="work/questions.json")
    args = ap.parse_args()

    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    planned_ids = {q["question_id"] for q in plan["questions"]}

    merged = {}
    for path in sorted(glob.glob(args.glob)):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        items = data if isinstance(data, list) else data.get("questions", [])
        for q in items:
            qid = q["question_id"]
            if qid in merged:
                sys.exit(f"[FAIL] duplicate question_id {qid} across chunks")
            merged[qid] = q

    got_ids = set(merged)
    missing = planned_ids - got_ids
    extra = got_ids - planned_ids
    if missing:
        sys.exit(f"[FAIL] missing questions for ids: {sorted(missing)}")
    if extra:
        sys.exit(f"[FAIL] unexpected ids not in plan: {sorted(extra)}")

    questions = [merged[i] for i in sorted(merged)]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

    print(f"[PASS] merged {len(questions)} questions -> {args.out}")


if __name__ == "__main__":
    main()
