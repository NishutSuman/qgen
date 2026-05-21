#!/usr/bin/env python3
"""validate_plan.py — Phase 1 gate.

HARD-STOP unless plan.json's difficulty histogram, count, and IDs match the
validated command. Run AFTER the orchestrator writes plan.json, BEFORE spawning
creation agents.

Usage:
    python scripts/validate_plan.py --plan plan.json --command work/command.json
"""
import argparse
import json
import sys


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--command", default="work/command.json")
    args = ap.parse_args()

    cmd = load(args.command)
    plan = load(args.plan)
    qs = plan.get("questions", [])

    errors = []

    # count
    if len(qs) != cmd["count"]:
        errors.append(f"plan has {len(qs)} questions, command wants {cmd['count']}")

    # difficulty histogram
    hist = {}
    for q in qs:
        key = str(q.get("difficulty"))
        hist[key] = hist.get(key, 0) + 1
    want = {str(k): v for k, v in cmd["difficulty_ratio"].items()}
    if hist != want:
        errors.append(f"difficulty mismatch: plan={hist} command={want}")

    # ids unique + contiguous from id_start
    ids = [q.get("question_id") for q in qs]
    if len(set(ids)) != len(ids):
        errors.append("duplicate question_id values in plan")
    expected_ids = list(range(cmd["id_start"], cmd["id_start"] + len(qs)))
    if sorted(ids) != expected_ids:
        errors.append(
            f"ids not contiguous from {cmd['id_start']} "
            f"(got {min(ids)}..{max(ids)} with gaps/dupes)"
        )

    # type must be mcsc
    bad_types = [q["question_id"] for q in qs if q.get("type") != "mcsc"]
    if bad_types:
        errors.append(f"non-mcsc type on ids {bad_types}")

    # topic family spread — no single family should exceed 30% (warn at 20%)
    family_counts: dict[str, int] = {}
    for q in qs:
        family = q.get("topic", "unknown").split("/")[0].strip()
        family_counts[family] = family_counts.get(family, 0) + 1
    if qs:
        for fam, cnt in sorted(family_counts.items(), key=lambda x: -x[1]):
            pct = cnt / len(qs)
            if pct > 0.30:
                errors.append(
                    f"topic family '{fam}' has {cnt}/{len(qs)} questions "
                    f"({pct:.0%}), exceeds 30% hard cap"
                )
            elif pct > 0.20:
                print(f"[WARN] topic family '{fam}' has {cnt}/{len(qs)} questions "
                      f"({pct:.0%}) — consider spreading further (soft cap 20%)")

    if errors:
        print("[FAIL] plan.json does not match command:")
        for e in errors:
            print("   -", e)
        sys.exit(1)

    print(f"[PASS] plan valid: {len(qs)} questions, difficulty {hist}")


if __name__ == "__main__":
    main()
