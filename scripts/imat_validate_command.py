#!/usr/bin/env python3
"""imat_validate_command.py — IMAT Phase 0 (HARD STOP).

Validate the IMAT generation command and freeze it to work/imat/command.json.

Rules:
  - --paper must be MBA or BS (selects a fixed blueprint variant).
  - --count is OPTIONAL. If given it must be within ±flex_pct (default 5%) of the
    variant's base_count. The difference is absorbed entirely by the blueprint's
    flex group (the QA MCQ pool). Difficulty mix is FIXED — it never changes.

Usage:
    python scripts/imat_validate_command.py --paper MBA [--count 70] \
        --blueprints imat/blueprints.json --out work/imat/command.json
"""
import argparse
import json
import math
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True,
                    help="blueprint variant key (e.g. MBA, BS, MICAT)")
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--tita", type=int, default=None,
                    help="number of TITA questions (within tita_range, default base)")
    ap.add_argument("--blueprints", default="imat/blueprints.json")
    ap.add_argument("--out", default="work/imat/command.json")
    args = ap.parse_args()

    with open(args.blueprints, encoding="utf-8") as f:
        bp = json.load(f)
    flex_pct = bp.get("flex_pct", 0.05)
    variant = bp["variants"].get(args.paper)
    if not variant:
        sys.exit(f"[FAIL] no blueprint for paper '{args.paper}'")

    base = variant["base_count"]
    requested = args.count if args.count is not None else base
    lo = math.floor(base * (1 - flex_pct))
    hi = math.ceil(base * (1 + flex_pct))
    if not (lo <= requested <= hi):
        sys.exit(
            f"[FAIL] --count {requested} outside ±{int(flex_pct*100)}% of "
            f"{args.paper} base {base} (allowed {lo}..{hi}). "
            f"Difficulty/structure are fixed per variant."
        )

    flex_groups = [g for g in variant["groups"] if g.get("flex")]
    if requested != base and not flex_groups:
        sys.exit("[FAIL] count delta requested but blueprint has no flex group")
    delta = requested - base

    # TITA pool sizing (within tita_range), compensated by the MCQ flex pool.
    # Variants without a TITA pool (e.g. MICAT) simply skip this.
    tita_groups = [g for g in variant["groups"] if g.get("tita_flex")]
    tita_base = sum(sum(g["difficulty"].values()) for g in tita_groups)
    if args.tita is not None:
        if not tita_groups:
            sys.exit("[FAIL] --tita given but this variant has no TITA pool")
        lo_t, hi_t = bp.get("tita_range", [tita_base, tita_base])
        if not (lo_t <= args.tita <= hi_t):
            sys.exit(f"[FAIL] --tita {args.tita} outside allowed range {lo_t}..{hi_t}")
        tita_target = args.tita
    else:
        tita_target = tita_base
    tita_delta = tita_target - tita_base
    if tita_delta and not flex_groups:
        sys.exit("[FAIL] --tita change needs an MCQ flex pool to compensate")
    # MCQ flex pool absorbs the count delta minus the TITA delta (keeps total = requested)
    mcq_delta = delta - tita_delta
    if flex_groups:
        mcq_base = sum(sum(g["difficulty"].values()) for g in flex_groups)
        if mcq_base + mcq_delta < 1:
            sys.exit(f"[FAIL] flex pool would drop below 1 (base {mcq_base}, delta {mcq_delta})")

    # section order for the plan gate: variant exam override, else group order
    exam = variant.get("exam") or bp.get("exam") or {}
    section_order = exam.get("section_order")
    if not section_order:
        section_order = list(dict.fromkeys(g["section"] for g in variant["groups"]))

    payload = {
        "paper": args.paper,
        "label": variant["label"],
        "base_count": base,
        "requested_count": requested,
        "flex_delta": delta,
        "mcq_delta": mcq_delta,
        "tita_delta": tita_delta,
        "tita_target": tita_target,
        "flex_group": flex_groups[0]["group_id"] if flex_groups else None,
        "section_order": section_order,
        "blueprints": args.blueprints,
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"[PASS] IMAT command valid: {args.paper}, count {requested} "
          f"(base {base}, delta {delta:+d}); TITA {tita_target} "
          f"(MCQ pool delta {mcq_delta:+d}) -> {args.out}")


if __name__ == "__main__":
    main()
