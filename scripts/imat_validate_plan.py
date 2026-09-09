#!/usr/bin/env python3
"""imat_validate_plan.py — IMAT Phase 1 gate (HARD STOP).

Validate the generated plan against the command + structural invariants:
  - total count == requested_count (already within ±5% by Phase 0)
  - section order is VARC, then DILR, then QA
  - shared sets: contiguous question_ids, set_seq 1..size, same set_id/kind
  - question_type in {mcsc, tita}; mcsc num_options in {4,5}; tita num_options 0
  - difficulty in {0, 0.5, 1}
  - question_ids unique and contiguous from 1

Usage:
    python scripts/imat_validate_plan.py --plan work/imat/plan.json \
        --command work/imat/command.json
"""
import argparse
import json
import sys

VALID_DIFF = {0, 0.5, 1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="work/imat/plan.json")
    ap.add_argument("--command", default="work/imat/command.json")
    args = ap.parse_args()

    with open(args.command, encoding="utf-8") as f:
        cmd = json.load(f)
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    qs = plan["questions"]
    errors = []
    section_order = cmd.get("section_order") or []

    if len(qs) != cmd["requested_count"]:
        errors.append(f"count {len(qs)} != requested {cmd['requested_count']}")

    ids = [q["question_id"] for q in qs]
    if ids != list(range(1, len(qs) + 1)):
        errors.append("question_ids not contiguous from 1")

    # section ordering must follow the blueprint's declared order
    seen_order, last = [], None
    for q in qs:
        if q["section"] != last:
            seen_order.append(q["section"])
            last = q["section"]
    if section_order and seen_order != [s for s in section_order if s in seen_order]:
        errors.append(f"sections not in declared order {section_order}: {seen_order}")

    # type / options / difficulty
    for q in qs:
        qt = q["question_type"]
        if qt not in {"mcsc", "tita"}:
            errors.append(f"Q{q['question_id']}: bad question_type {qt}")
        if qt == "mcsc" and q["num_options"] not in (4, 5):
            errors.append(f"Q{q['question_id']}: mcsc num_options must be 4 or 5")
        if qt == "tita" and q["num_options"] != 0:
            errors.append(f"Q{q['question_id']}: tita must have num_options 0")
        if q["difficulty"] not in VALID_DIFF:
            errors.append(f"Q{q['question_id']}: bad difficulty {q['difficulty']}")

    # shared set integrity
    sets = {}
    for q in qs:
        if q["shared_set"]:
            sets.setdefault(q["set_id"], []).append(q)
    for sid, members in sets.items():
        members_sorted = sorted(members, key=lambda x: x["question_id"])
        mids = [m["question_id"] for m in members_sorted]
        if mids != list(range(mids[0], mids[0] + len(mids))):
            errors.append(f"set {sid}: question_ids not contiguous {mids}")
        if [m["set_seq"] for m in members_sorted] != list(range(1, len(members_sorted) + 1)):
            errors.append(f"set {sid}: set_seq not 1..{len(members_sorted)}")
        if any(m["set_size"] != len(members_sorted) for m in members_sorted):
            errors.append(f"set {sid}: set_size mismatch")
        if len({m["kind"] for m in members_sorted}) != 1:
            errors.append(f"set {sid}: mixed kinds")

    if errors:
        print("[FAIL] IMAT plan invalid:")
        for e in errors:
            print("   -", e)
        sys.exit(1)

    print(f"[PASS] IMAT plan valid: {len(qs)} questions, "
          f"{len(sets)} shared set(s)")


if __name__ == "__main__":
    main()
