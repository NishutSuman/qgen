#!/usr/bin/env python3
"""imat_shuffle_options.py — IMAT option shuffler + position balancer.

Shuffles mcsc options and balances the correct-answer position across the paper.
IMAT specifics:
  - tita questions are skipped (no options).
  - 4-option and 5-option mcsc are balanced SEPARATELY (4-opt over positions 1-4,
    5-opt over 1-5) so neither distribution is skewed by the other.
  - Question ORDER is never changed (set integrity); only options within a
    question move. correct_answer and verification.expected are updated.

Run AFTER Phase 5, BEFORE export. The LLM must NOT balance positions by hand.

Usage:
    python scripts/imat_shuffle_options.py --in work/imat/questions.json [--seed 42]
"""
import argparse
import json
import random
from collections import Counter


def balanced_positions(n, num_opts, rng):
    base, extra = divmod(n, num_opts)
    counts = [base + 1 if i < extra else base for i in range(num_opts)]
    positions = []
    for idx, c in enumerate(counts):
        positions.extend([idx + 1] * c)
    rng.shuffle(positions)
    return positions


def repoint_verification(q, old_pos, new_pos):
    """Keep verification valid after a move: the expr's success literal encodes
    the correct option's position (drafted as '<old_pos>'); repoint it to the new
    position so recompute_answers stays consistent post-shuffle. Updates expected too.
    """
    v = q.get("verification")
    if not v or old_pos == new_pos:
        if v and "expected" in v:
            v["expected"] = str(new_pos)
        return
    expr = v.get("expr", "")
    if expr:
        segs = expr.split(";")
        last = segs[-1]
        for quote in ("'", '"'):
            token = f"{quote}{old_pos}{quote}"
            if token in last:                     # replace only the success literal
                segs[-1] = last.replace(token, f"{quote}{new_pos}{quote}", 1)
                v["expr"] = ";".join(segs)
                break
    if "expected" in v:
        v["expected"] = str(new_pos)


def shuffle_to(q, target, rng):
    n = q["num_options"]
    opts = q["options"]
    old = str(q["correct_answer"])
    correct_text = opts[old]
    others = [opts[str(i)] for i in range(1, n + 1) if str(i) != old]
    rng.shuffle(others)
    new_opts, it = {}, iter(others)
    for pos in range(1, n + 1):
        new_opts[str(pos)] = correct_text if pos == target else next(it)
    q["options"] = new_opts
    q["correct_answer"] = str(target)
    repoint_verification(q, old, str(target))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/imat/questions.json")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else random.randint(0, 2**32 - 1)
    rng = random.Random(seed)
    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    by_n = {}
    for q in qs:
        if q.get("question_type") == "mcsc":
            by_n.setdefault(q["num_options"], []).append(q)

    summary = {}
    for n, group in sorted(by_n.items()):
        targets = balanced_positions(len(group), n, rng)
        for q, t in zip(group, targets):
            shuffle_to(q, t, rng)
        summary[f"{n}-option"] = dict(Counter(int(q["correct_answer"]) for q in group))

    with open(args.inp, "w", encoding="utf-8") as f:
        json.dump(qs, f, indent=2, ensure_ascii=False)

    print(f"[OK] IMAT shuffled (seed={seed}) -> {args.inp}")
    for k, dist in summary.items():
        print(f"     {k}: {dict(sorted(dist.items()))}")


if __name__ == "__main__":
    main()
