#!/usr/bin/env python3
"""shuffle_options.py — Deterministic option shuffler with balanced position distribution.

Shuffles the 4 options of every question randomly, updates correct_answer and
verification.expected to match the new positions, then enforces that the correct
answer is distributed as evenly as possible across positions 1-4 across the
whole paper.

Must run AFTER Phase 5 (final mechanical checks) and BEFORE export_csv.py.
The LLM must NOT attempt to balance answer positions — this script owns that.

Usage:
    python scripts/shuffle_options.py --in work/questions.json --seed 42
        (modifies in place; seed makes the run reproducible)
    python scripts/shuffle_options.py --in work/questions.json
        (random seed, noted in stdout)
"""
import argparse
import json
import random
import sys


def balanced_positions(n: int, rng: random.Random) -> list[int]:
    """Return a list of n positions (1-4) distributed as evenly as possible.

    For n=50: positions 1 and 2 get 13 each, positions 3 and 4 get 12 each
    (or any permutation thereof), then the list is shuffled so assignment
    order is random.
    """
    base, extra = divmod(n, 4)
    # First `extra` positions get (base+1) slots, the rest get base slots
    counts = [base + 1 if i < extra else base for i in range(4)]
    positions = []
    for pos_idx, count in enumerate(counts):
        positions.extend([pos_idx + 1] * count)
    rng.shuffle(positions)
    return positions


def shuffle_question(q: dict, target_pos: int, rng: random.Random) -> None:
    """Shuffle q's options so correct_answer lands on target_pos.

    Updates q in place: options dict, correct_answer, verification.expected.
    Never touches question_text, explanation, difficulty, timings, or
    discrimination_ratio.
    """
    opts = q["options"]
    old_correct = str(q["correct_answer"])
    correct_text = opts[old_correct]
    others = [opts[str(i)] for i in range(1, 5) if str(i) != old_correct]
    rng.shuffle(others)

    new_opts: dict[str, str] = {}
    other_iter = iter(others)
    for pos in range(1, 5):
        if pos == target_pos:
            new_opts[str(pos)] = correct_text
        else:
            new_opts[str(pos)] = next(other_iter)

    q["options"] = new_opts
    q["correct_answer"] = str(target_pos)
    if "verification" in q and "expected" in q.get("verification", {}):
        q["verification"]["expected"] = str(target_pos)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/questions.json")
    ap.add_argument("--seed", type=int, default=None,
                    help="Random seed for reproducibility")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else random.randint(0, 2**32 - 1)
    rng = random.Random(seed)

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    n = len(qs)
    target_positions = balanced_positions(n, rng)

    for q, target_pos in zip(qs, target_positions):
        shuffle_question(q, target_pos, rng)

    with open(args.inp, "w", encoding="utf-8") as f:
        json.dump(qs, f, indent=2, ensure_ascii=False)

    # Report final distribution
    from collections import Counter
    dist = Counter(int(q["correct_answer"]) for q in qs)
    dist_str = "  ".join(f"pos{p}={dist[p]}" for p in sorted(dist))
    longest_pct = max(dist.values()) / n * 100
    print(f"[OK] shuffled {n} questions (seed={seed}) -> {args.inp}")
    print(f"     distribution: {dist_str}  longest-correct={longest_pct:.1f}%")


if __name__ == "__main__":
    main()
