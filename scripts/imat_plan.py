#!/usr/bin/env python3
"""imat_plan.py — IMAT Phase 1 (plan generation).

Deterministically expand the chosen blueprint variant into a per-question plan
(intent only, like qgen's plan.json). Applies the ±5% flex delta to the flex
group's medium ("0.5") bucket. Difficulty levels are otherwise untouched.

Each question slot carries its section, set grouping, type, option count, topic
and difficulty. A group with kind != 'none' is a SHARED SET (one stimulus, one
platform config); kind 'none' groups are singletons.

Usage:
    python scripts/imat_plan.py --command work/imat/command.json \
        --out work/imat/plan.json
"""
import argparse
import json
import os
import sys


def apply_flex(group, delta):
    """Return a difficulty dict for the flex group adjusted by delta."""
    dist = dict(group["difficulty"])
    if delta == 0:
        return dist
    bucket = "0.5" if "0.5" in dist else next(iter(dist))
    dist[bucket] = dist.get(bucket, 0) + delta
    if dist[bucket] < 0:
        sys.exit(f"[FAIL] flex delta {delta} drives {group['group_id']} "
                 f"bucket '{bucket}' negative")
    return dist


def expand_difficulty(dist):
    """{'0.5':2,'1':1} -> ['0.5','0.5','1'] (stable, sorted by level)."""
    out = []
    for level in sorted(dist, key=lambda x: float(x)):
        out += [level] * dist[level]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--command", default="work/imat/command.json")
    ap.add_argument("--out", default="work/imat/plan.json")
    args = ap.parse_args()

    with open(args.command, encoding="utf-8") as f:
        cmd = json.load(f)
    with open(cmd["blueprints"], encoding="utf-8") as f:
        bp = json.load(f)
    variant = bp["variants"][cmd["paper"]]

    questions = []
    qid = 1
    for g in variant["groups"]:
        if g.get("flex"):
            dist = apply_flex(g, cmd.get("mcq_delta", cmd.get("flex_delta", 0)))
        elif g.get("tita_flex"):
            dist = apply_flex(g, cmd.get("tita_delta", 0))
        else:
            dist = g["difficulty"]
        levels = expand_difficulty(dist)
        size = len(levels)
        shared = g["kind"] != "none"
        for seq, level in enumerate(levels, start=1):
            set_id = g["group_id"] if shared else f"{g['group_id']}-{seq}"
            slot = {
                "question_id": qid,
                "section": g["section"],
                "group_id": g["group_id"],
                "set_id": set_id,
                "set_seq": seq if shared else 1,
                "set_size": size if shared else 1,
                "shared_set": shared,
                "kind": g["kind"],
                "question_type": g["qtype"],
                "num_options": g["num_options"],
                "topic": g["topic"],
                "difficulty": float(level) if level != "0" else 0,
            }
            # Set-level candidate instruction (CSV only). Carried from the
            # blueprint so every question of a set repeats it — each question is
            # uploaded standalone, so it must say what to do with the stimulus.
            if g.get("instruction"):
                slot["instruction"] = g["instruction"]
            questions.append(slot)
            qid += 1

    meta = {
        "paper": cmd["paper"],
        "label": cmd["label"],
        "count": len(questions),
        "requested_count": cmd["requested_count"],
        "sections": {},
    }
    for q in questions:
        meta["sections"][q["section"]] = meta["sections"].get(q["section"], 0) + 1

    if len(questions) != cmd["requested_count"]:
        sys.exit(f"[FAIL] plan produced {len(questions)} != requested "
                 f"{cmd['requested_count']}")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "questions": questions}, f, indent=2, ensure_ascii=False)

    print(f"[PASS] IMAT plan: {len(questions)} questions "
          f"({', '.join(f'{k} {v}' for k, v in meta['sections'].items())}) -> {args.out}")


if __name__ == "__main__":
    main()
