#!/usr/bin/env python3
"""imat_merge_chunks.py — IMAT Phase 2 merge.

Combine work/imat/questions_chunk_*.json into work/imat/questions.json (sorted by
question_id) and enforce IMAT structural invariants:

  - every planned question_id present exactly once; no extras
  - each record carries plan fields (section, set_id, set_seq, kind, type, ...)
  - mcsc: exactly num_options non-empty options "1".."N"; correct_answer is one
    of them.  tita: a non-empty tita_answer and no options.
  - SHARED SETS: every member carries the stimulus, and the stimulus (kind +
    markdown + chart) is IDENTICAL across the set — because each question is
    uploaded separately and must be self-contained.

Usage:
    python scripts/imat_merge_chunks.py --plan work/imat/plan.json \
        --glob "work/imat/questions_chunk_*.json" --out work/imat/questions.json
"""
import argparse
import glob
import json
import sys


def stim_key(q):
    s = q.get("stimulus") or {}
    return (s.get("kind"), s.get("markdown"), json.dumps(s.get("chart"), sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="work/imat/plan.json")
    ap.add_argument("--glob", default="work/imat/questions_chunk_*.json")
    ap.add_argument("--out", default="work/imat/questions.json")
    args = ap.parse_args()

    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    planned = {q["question_id"]: q for q in plan["questions"]}

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

    missing = set(planned) - set(merged)
    extra = set(merged) - set(planned)
    if missing:
        sys.exit(f"[FAIL] missing questions for ids: {sorted(missing)}")
    if extra:
        sys.exit(f"[FAIL] unexpected ids not in plan: {sorted(extra)}")

    errors = []
    for qid, q in merged.items():
        p = planned[qid]
        # carry plan structure forward (authoritative)
        for k in ("section", "set_id", "set_seq", "set_size", "shared_set",
                  "kind", "question_type", "num_options", "topic", "difficulty"):
            q[k] = p[k]
        if p.get("instruction"):          # blueprint-owned candidate instruction
            q["instruction"] = p["instruction"]
        qt = q["question_type"]
        if qt == "mcsc":
            opts = q.get("options") or {}
            keys = [str(i) for i in range(1, p["num_options"] + 1)]
            if sorted(opts.keys()) != sorted(keys) or any(not str(opts[k]).strip() for k in keys):
                errors.append(f"Q{qid}: needs {p['num_options']} non-empty options")
            if str(q.get("correct_answer")) not in keys:
                errors.append(f"Q{qid}: correct_answer not in 1..{p['num_options']}")
        elif qt == "tita":
            if q.get("options"):
                errors.append(f"Q{qid}: tita must not have options")
            if str(q.get("tita_answer", "")).strip() == "":
                errors.append(f"Q{qid}: tita missing tita_answer")
        if q["shared_set"]:
            s = q.get("stimulus") or {}
            if not (s.get("markdown") or s.get("chart")):
                errors.append(f"Q{qid}: shared-set question missing stimulus")

    # stimulus identical within each shared set
    sets = {}
    for q in merged.values():
        if q["shared_set"]:
            sets.setdefault(q["set_id"], []).append(q)
    for sid, members in sets.items():
        if len({stim_key(m) for m in members}) != 1:
            errors.append(f"set {sid}: stimulus differs across members "
                          f"(must be identical — each Q is uploaded standalone)")

    if errors:
        print("[FAIL] IMAT merge problems:")
        for e in errors:
            print("   -", e)
        sys.exit(1)

    questions = [merged[i] for i in sorted(merged)]
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    print(f"[PASS] merged {len(questions)} IMAT questions, {len(sets)} shared "
          f"set(s) -> {args.out}")


if __name__ == "__main__":
    main()
