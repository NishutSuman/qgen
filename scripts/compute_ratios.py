#!/usr/bin/env python3
"""compute_ratios.py — derived field.

discrimination_ratio = round(t_average_sec / t_expert_sec, 1)

Never authored by hand; always computed here. Warns on out-of-band values.

Usage:
    python scripts/compute_ratios.py --in work/questions.json
"""
import argparse
import json

LOW, HIGH = 2.5, 12.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/questions.json")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    warnings = []
    for q in qs:
        te = q.get("t_expert_sec")
        ta = q.get("t_average_sec")
        if not te or not ta:
            warnings.append(f"Q{q['question_id']}: missing timing values")
            continue
        if ta <= te:
            warnings.append(f"Q{q['question_id']}: t_average ({ta}) <= t_expert ({te})")
        ratio = round(ta / te, 1)
        q["discrimination_ratio"] = ratio
        if not (LOW <= ratio <= HIGH):
            warnings.append(f"Q{q['question_id']}: ratio {ratio} outside [{LOW},{HIGH}]")

    with open(args.inp, "w", encoding="utf-8") as f:
        json.dump(qs, f, indent=2, ensure_ascii=False)

    print(f"[OK] computed discrimination_ratio for {len(qs)} questions")
    for w in warnings:
        print("   [warn]", w)


if __name__ == "__main__":
    main()
