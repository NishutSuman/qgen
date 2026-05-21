#!/usr/bin/env python3
"""mechanical_checks.py — Phases 3 & 5 (deterministic).

Runs M1-M7, applies deterministic auto-fixes, rewrites the file, and emits a
report. Call repeatedly (orchestrator caps the cycle count).

  M1 Longest-correct      batch tolerance <=10% ; auto-fix surplus by reshuffle
  M2 Answer-position      each option 10%-40% ; auto-fix by reshuffle
  M3 Surface-cue leak     correct option not uniquely marked ; flag
  M4 Structure            4 non-empty unique options, valid index ; flag
  M5 Near-duplicate stems Jaccard>0.8 ; flag later one
  M6 Encoding/LaTeX       no \\uXXXX, balanced $, no \\frac{}{} comma ; auto-fix escapes
  M7 Ratio sanity         2.5<=DR<=12 and t_avg>t_expert ; flag

Usage:
    python scripts/mechanical_checks.py --in work/questions.json \
        --report work/mech_report.json [--seed 7] [--no-fix]
"""
import argparse
import json
import random
import re

LONGEST_TOLERANCE = 0.10
POS_MIN, POS_MAX = 0.10, 0.40
JACCARD_DUP = 0.8
RATIO_LOW, RATIO_HIGH = 2.5, 12.0
UNICODE_FIXES = {
    "\\u20b9": "₹", "\\u00d7": "×", "\\u00f7": "÷", "\\u2212": "−",
    "\\u2192": "→", "\\u221a": "√", "\\u03c0": "π", "\\u00b0": "°",
}


def norm_len(s: str) -> int:
    return len(re.sub(r"\s+", "", s or ""))


def tokens(s: str):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def jaccard(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def reshuffle(q, rng):
    """Randomly permute the 4 options and update correct_answer."""
    opts = [q["options"][str(i)] for i in range(1, 5)]
    correct_text = q["options"][str(q["correct_answer"])]
    order = [0, 1, 2, 3]
    rng.shuffle(order)
    new_opts = {str(i + 1): opts[order[i]] for i in range(4)}
    q["options"] = new_opts
    for i in range(1, 5):
        if new_opts[str(i)] == correct_text:
            q["correct_answer"] = str(i)
            break


# ---- surface cue helpers (M3) ----
def has_units(s):
    return bool(re.search(r"\d\s*(cm|km|m|kg|g|s|%|°|₹|\$|hours|days|years)\b", s or "")
                or re.search(r"(cm|km|kg)²?$", (s or "").strip()))


def has_paren(s):
    return "(" in (s or "")


def has_symbol(s):
    return bool(re.search(r"[×÷√π°%₹$≤≥≠→]", s or ""))


def terminal_punct(s):
    return (s or "").strip().endswith((".", "!", "?"))


def cue_profile(opt):
    return (has_units(opt), has_paren(opt), has_symbol(opt), terminal_punct(opt))


def check(qs, fix, rng):
    report = {"M1": [], "M2": [], "M3": [], "M4": [], "M5": [], "M6": [], "M7": []}

    # ---- M6 encoding/LaTeX (auto-fix escapes) ----
    for q in qs:
        for field in ["question_text", "explanation"]:
            txt = q.get(field, "")
            if any(k in txt for k in UNICODE_FIXES) or "\\u" in txt:
                if fix:
                    for k, v in UNICODE_FIXES.items():
                        txt = txt.replace(k, v)
                    q[field] = txt
                report["M6"].append({"id": q["question_id"], "field": field,
                                      "issue": "unicode escape", "fixed": fix})
            if re.search(r"\\frac\{[^}]*\},\{", q.get(field, "")):
                report["M6"].append({"id": q["question_id"], "field": field,
                                      "issue": "\\frac{}{} comma corruption", "fixed": False})
            if q.get(field, "").count("$") % 2 != 0:
                report["M6"].append({"id": q["question_id"], "field": field,
                                      "issue": "unbalanced $", "fixed": False})

    # ---- M4 structure ----
    for q in qs:
        opts = q.get("options", {})
        vals = [opts.get(str(i), "") for i in range(1, 5)]
        problems = []
        if len(opts) != 4 or any(not v.strip() for v in vals):
            problems.append("not 4 non-empty options")
        if len(set(v.strip() for v in vals)) != 4:
            problems.append("duplicate option text")
        if str(q.get("correct_answer")) not in {"1", "2", "3", "4"}:
            problems.append("invalid correct_answer index")
        if problems:
            report["M4"].append({"id": q["question_id"], "problems": problems})

    # ---- M3 surface-cue leak ----
    for q in qs:
        opts = q.get("options", {})
        if len(opts) != 4:
            continue
        ca = str(q.get("correct_answer"))
        profiles = {i: cue_profile(opts[str(i)]) for i in range(1, 5) if str(i) in opts}
        for dim, name in enumerate(["units", "paren", "symbol", "punct"]):
            flags = {i: p[dim] for i, p in profiles.items()}
            # leak = correct option is the ONLY one with this cue
            if flags.get(int(ca)) and sum(flags.values()) == 1:
                report["M3"].append({"id": q["question_id"], "cue": name,
                                     "note": "only correct option carries this cue"})

    # ---- M1 longest-correct (batch tolerance) ----
    longest_correct_ids = []
    for q in qs:
        opts = q.get("options", {})
        if len(opts) != 4:
            continue
        lens = {i: norm_len(opts[str(i)]) for i in range(1, 5)}
        ca = int(q.get("correct_answer", 0))
        if ca in lens and lens[ca] == max(lens.values()) and \
                list(lens.values()).count(max(lens.values())) == 1:
            longest_correct_ids.append(q["question_id"])
    frac = len(longest_correct_ids) / max(1, len(qs))
    if frac > LONGEST_TOLERANCE:
        # fix the surplus by reshuffling those questions
        surplus = int(round((frac - LONGEST_TOLERANCE) * len(qs)))
        to_fix = longest_correct_ids[-surplus:] if surplus > 0 else []
        for q in qs:
            entry = {"id": q["question_id"], "in_surplus": q["question_id"] in to_fix}
            if q["question_id"] in longest_correct_ids:
                report["M1"].append(entry)
            if fix and q["question_id"] in to_fix:
                reshuffle(q, rng)
        report["M1"].append({"batch_longest_correct_pct": round(frac * 100, 1),
                             "tolerance_pct": LONGEST_TOLERANCE * 100,
                             "auto_reshuffled": to_fix})
    else:
        report["M1"].append({"batch_longest_correct_pct": round(frac * 100, 1),
                             "tolerance_pct": LONGEST_TOLERANCE * 100,
                             "status": "within tolerance"})

    # ---- M2 answer-position balance ----
    def position_hist():
        h = {1: 0, 2: 0, 3: 0, 4: 0}
        for q in qs:
            try:
                h[int(q["correct_answer"])] += 1
            except (ValueError, KeyError):
                pass
        return h

    hist = position_hist()
    n = max(1, len(qs))
    over = [p for p, c in hist.items() if c / n > POS_MAX]
    under = [p for p, c in hist.items() if c / n < POS_MIN]
    if over or under:
        report["M2"].append({"histogram": hist, "over": over, "under": under})
        if fix and over:
            # reshuffle some questions whose answer sits in an over-used position
            for p in over:
                movers = [q for q in qs if int(q["correct_answer"]) == p]
                # move roughly half
                for q in movers[: len(movers) // 2]:
                    reshuffle(q, rng)
            report["M2"].append({"post_fix_histogram": position_hist()})

    # ---- M5 near-duplicate stems ----
    for i in range(len(qs)):
        for j in range(i + 1, len(qs)):
            if jaccard(qs[i].get("question_text"), qs[j].get("question_text")) > JACCARD_DUP:
                report["M5"].append({"pair": [qs[i]["question_id"], qs[j]["question_id"]],
                                     "flag_for_regen": qs[j]["question_id"]})

    # ---- M7 ratio sanity ----
    for q in qs:
        te, ta = q.get("t_expert_sec"), q.get("t_average_sec")
        dr = q.get("discrimination_ratio")
        issues = []
        if te and ta and ta <= te:
            issues.append("t_average <= t_expert")
        if dr is not None and not (RATIO_LOW <= dr <= RATIO_HIGH):
            issues.append(f"DR {dr} out of [{RATIO_LOW},{RATIO_HIGH}]")
        if issues:
            report["M7"].append({"id": q["question_id"], "issues": issues})

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/questions.json")
    ap.add_argument("--report", default="work/mech_report.json")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--no-fix", action="store_true")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    report = check(qs, fix=not args.no_fix, rng=rng)

    if not args.no_fix:
        with open(args.inp, "w", encoding="utf-8") as f:
            json.dump(qs, f, indent=2, ensure_ascii=False)

    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # flags that block "clean" status (non-auto-fixable)
    blocking = (
        len(report["M4"]) + len(report["M5"]) +
        sum(1 for x in report["M6"] if not x.get("fixed", False)) +
        len(report["M3"]) + len(report["M7"])
    )
    print(f"[OK] mechanical report -> {args.report}")
    print(f"   M1 longest-correct : {report['M1'][-1]}")
    print(f"   M2 position        : {'OK' if not report['M2'] else report['M2'][0]}")
    print(f"   M3 cue leaks       : {len(report['M3'])}")
    print(f"   M4 structure       : {len(report['M4'])}")
    print(f"   M5 duplicates      : {len(report['M5'])}")
    print(f"   M6 encoding        : {len(report['M6'])}")
    print(f"   M7 ratio           : {len(report['M7'])}")
    print(f"   BLOCKING (need attention): {blocking}")


if __name__ == "__main__":
    main()
