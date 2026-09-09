#!/usr/bin/env python3
"""recompute_answers.py — Phase 4 correctness gate.

Independent verification of numeric/closed-form answers. The creation agent
SHOULD attach a `verification` block to every question it can:

    "verification": {
        "expr": "1 if (900/60==15 and 18-15==3) else 0; '3' if round((18-15)/15*100)==20 else '0'",
        "expected": "3"
    }

More usefully, `expr` is a small Python snippet whose LAST expression evaluates
to the correct option string ("1".."4"). It runs in a restricted namespace with
math, fractions.Fraction, itertools, and comb available. The script checks that
the evaluated value equals BOTH `verification.expected` and the question's
`correct_answer`.

Questions with no verification block (pure verbal/logic) are reported as
UNCHECKABLE and must be cleared by the QC skill instead.

Usage:
    python scripts/recompute_answers.py --in work/questions.json \
        --report work/recompute_report.json
Exit code is 0 always; read the report for MISMATCH items.
"""
import argparse
import json
import math
from fractions import Fraction
import itertools
from itertools import combinations, permutations, product
from math import comb, factorial, gcd

SAFE = {
    "__builtins__": {
        "abs": abs, "round": round, "min": min, "max": max, "sum": sum,
        "len": len, "range": range, "sorted": sorted, "int": int,
        "float": float, "set": set, "list": list, "tuple": tuple, "all": all,
        "any": any, "map": map, "filter": filter, "str": str, "pow": pow,
        # pure-data helpers: needed by ordinary verification snippets
        "dict": dict, "zip": zip, "enumerate": enumerate, "next": next,
        "reversed": reversed, "divmod": divmod, "bool": bool,
    },
    "math": math, "Fraction": Fraction, "gcd": gcd, "comb": comb,
    "factorial": factorial, "combinations": combinations,
    "permutations": permutations, "product": product, "itertools": itertools,
}


def run_expr(expr: str):
    """Evaluate the last expression of a small snippet, restricted namespace.

    All segments share ONE namespace (globals is locals). That matters: with
    separate globals/locals, a comprehension or lambda in a later segment cannot
    see names assigned by an earlier segment (they resolve against globals), so
    perfectly ordinary brute-force snippets blew up with NameError.
    """
    lines = [ln for ln in expr.strip().split(";") if ln.strip()]
    if not lines:
        raise ValueError("empty expr")
    body, last = lines[:-1], lines[-1]
    ns = dict(SAFE)
    for ln in body:
        ln = ln.strip()
        if not ln or ln.startswith(("import ", "from ")):
            continue  # skip import statements — names are pre-loaded in SAFE
        exec(ln, ns)  # noqa: S102 (local, user-owned pipeline)
    return eval(last.strip(), ns)  # noqa: S307


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/questions.json")
    ap.add_argument("--report", default="work/recompute_report.json")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    results = []
    for q in qs:
        qid = q["question_id"]
        v = q.get("verification")
        if not v or not v.get("expr"):
            results.append({"id": qid, "verdict": "UNCHECKABLE",
                            "note": "no verification block"})
            continue
        try:
            got = str(run_expr(v["expr"])).strip()
        except Exception as e:  # noqa: BLE001
            results.append({"id": qid, "verdict": "ERROR", "note": repr(e)})
            continue
        expected = str(v.get("expected", "")).strip()
        # mcsc carries correct_answer; IMAT tita carries tita_answer instead
        stated = str(q.get("correct_answer", q.get("tita_answer", ""))).strip()
        if got == expected == stated:
            results.append({"id": qid, "verdict": "MATCH"})
        else:
            results.append({
                "id": qid, "verdict": "MISMATCH",
                "computed": got, "verification_expected": expected,
                "stated_correct_answer": stated,
            })

    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    counts = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    print(f"[OK] recompute report -> {args.report}")
    print("   verdicts:", counts)
    for r in results:
        if r["verdict"] in ("MISMATCH", "ERROR"):
            print("   [!]", r)


if __name__ == "__main__":
    main()
