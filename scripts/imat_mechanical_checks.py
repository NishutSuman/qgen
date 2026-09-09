#!/usr/bin/env python3
"""imat_mechanical_checks.py — IMAT Phases 3 & 5 (deterministic).

IMAT-aware port of mechanical_checks.py. Handles mcsc (4 OR 5 options), tita
(no options), and shared-set stimuli. Answer-position balancing is owned by
imat_shuffle_options.py, so M1/M2 here are REPORT-ONLY (no reshuffle).

  M3  Surface-cue leak  correct mcsc option not uniquely marked (units/paren/symbol/punct)
  M4  Structure         mcsc: num_options non-empty distinct opts + valid key;
                        tita: non-empty tita_answer; explanation >= 50 chars
  M5  Near-dup prompts  Jaccard>0.8 on question_text across DIFFERENT sets
  M6  Encoding/LaTeX    no \\uXXXX, balanced $, no \\frac{}{} comma (auto-fix escapes)
  M7  Ratio sanity      2.5<=DR<=12 and t_avg>t_expert
  M8  Verify syntax     verification.expr compiles
  M9  Expected/answer   mcsc: expected==correct_answer ; tita: expected==tita_answer
  M10 Set integrity     shared set contiguous, identical stimulus, seq 1..n
  M11 Length bias       correct option must NOT be noticeably the longest (blocking,
                        route to creator) + batch cap on "correct is longest"
  M1  Longest-correct   batch % of mcsc where correct is uniquely longest (report)
  M2  Position balance  histogram of correct positions over mcsc (report)

Also: em/en dashes (—, –) are auto-stripped everywhere (M6) — an AI-writing tell
the paper must not contain.

Usage:
    python scripts/imat_mechanical_checks.py --in work/imat/questions.json \
        --report work/imat/mech_report.json [--no-fix]
"""
import argparse
import json
import re

LONGEST_TOLERANCE = 0.10
RATIO_LOW, RATIO_HIGH = 2.5, 12.0
JACCARD_DUP = 0.8
EXPLAIN_MIN_CHARS = 50
LEN_BIAS_MARGIN = 0.15     # correct option may not exceed the 2nd-longest by >15%
LEN_BIAS_MIN_ABS = 6       # ...AND by at least this many chars (spares proper-noun
                           # option sets, where a 1-char gap is not an exploitable tell)
LEN_BATCH_CAP = 0.30       # ≤30% of mcsc may have the correct option as longest
UNICODE_FIXES = {
    "\\u20b9": "₹", "\\u00d7": "×", "\\u00f7": "÷", "\\u2212": "−",
    "\\u2192": "→", "\\u221a": "√", "\\u03c0": "π", "\\u00b0": "°",
}
# em / en / figure / horizontal-bar dashes — an AI-writing tell; stripped entirely.
DASHES = "‒–—―"
# explanations must not cite option POSITIONS (the shuffle reorders options, so
# "Option 3" / "(C)" goes stale) — reference the value/content instead.
EXPL_POS_RE = re.compile(r"\b[Oo]ption\s*\(?\s*[1-5]\b|\b[Cc]hoice\s+[A-E]\b|\([A-E]\)|\bthe (first|second|third|fourth|last) (option|statement|choice)\b", re.I)


def strip_tells(t):
    """Remove unicode escapes and em/en dashes. Returns (clean, changed)."""
    if not t:
        return t, False
    orig = t
    for k, v in UNICODE_FIXES.items():
        t = t.replace(k, v)
    t = t.replace(" — ", ", ").replace(" – ", ", ")   # spaced dash -> comma
    t = re.sub(f"[{DASHES}]", "-", t)                           # any leftover -> hyphen
    return t, (t != orig)


def body_text(q):
    """Stimulus + prompt: set questions share short generic prompts, so comparing
    prompts alone falsely flags RC/DI items built on different passages/tables."""
    md = ((q.get("stimulus") or {}).get("markdown") or "")
    return (md + " " + (q.get("question_text") or "")).strip()


def norm_len(s):
    return len(re.sub(r"\s+", "", s or ""))


def tokens(s):
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def jaccard(a, b):
    ta, tb = tokens(a), tokens(b)
    return len(ta & tb) / len(ta | tb) if (ta and tb) else 0.0


def has_units(s):
    return bool(re.search(r"\d\s*(cm|km|m|kg|g|s|%|°|₹|\$|hours|days|years)\b", s or "")
                or re.search(r"(cm|km|kg)²?$", (s or "").strip()))


def cue_profile(opt):
    return (has_units(opt), "(" in (opt or ""),
            bool(re.search(r"[×÷√π°%₹$≤≥≠→]", opt or "")),
            (opt or "").strip().endswith((".", "!", "?")))


def opt_items(q):
    return [(k, v) for k, v in (q.get("options") or {}).items()]


def check(qs, fix):
    rep = {f"M{i}": [] for i in range(1, 12)}
    mcsc = [q for q in qs if q.get("question_type") == "mcsc"]

    # M6 encoding + dash tells (auto-fix across text fields, stimulus AND options)
    for q in qs:
        targets = [("question_text", q.get("question_text", "")),
                   ("explanation", q.get("explanation", ""))]
        if q.get("stimulus"):
            targets.append(("stimulus", q["stimulus"].get("markdown", "") or ""))
        for k, v in (q.get("options") or {}).items():
            targets.append((("option", k), v))
        for name, txt in targets:
            new, changed = strip_tells(txt)
            if changed:
                if fix:
                    if name == "stimulus":
                        q["stimulus"]["markdown"] = new
                    elif isinstance(name, tuple):
                        q["options"][name[1]] = new
                    else:
                        q[name] = new
                rep["M6"].append({"id": q["question_id"], "field": str(name),
                                  "issue": "unicode/dash tell", "fixed": fix})
            chk = new if fix else txt
            if re.search(r"\\frac\{[^}]*\},\{", chk):
                rep["M6"].append({"id": q["question_id"], "field": str(name),
                                  "issue": "\\frac{}{} comma", "fixed": False})
            if isinstance(name, str) and chk.count("$") % 2 != 0:
                rep["M6"].append({"id": q["question_id"], "field": str(name),
                                  "issue": "unbalanced $", "fixed": False})

    # M4 structure
    for q in qs:
        problems = []
        if q["question_type"] == "mcsc":
            n = q.get("num_options", 4)
            opts = q.get("options") or {}
            vals = [opts.get(str(i), "") for i in range(1, n + 1)]
            if len(opts) != n or any(not str(v).strip() for v in vals):
                problems.append(f"not {n} non-empty options")
            if len({str(v).strip() for v in vals}) != n:
                problems.append("duplicate option text")
            if str(q.get("correct_answer")) not in {str(i) for i in range(1, n + 1)}:
                problems.append("invalid correct_answer")
        else:  # tita
            if str(q.get("tita_answer", "")).strip() == "":
                problems.append("missing tita_answer")
        if norm_len(q.get("explanation", "")) < EXPLAIN_MIN_CHARS:
            problems.append("explanation too short")
        if EXPL_POS_RE.search(q.get("explanation", "")):
            problems.append("explanation cites an option position (use the value, "
                            "not 'Option N'/'(A)' — positions get shuffled)")
        if problems:
            rep["M4"].append({"id": q["question_id"], "problems": problems})

    # M3 surface-cue leak (mcsc only)
    for q in mcsc:
        opts = q.get("options") or {}
        ca = str(q.get("correct_answer"))
        profiles = {k: cue_profile(v) for k, v in opts.items()}
        for dim, name in enumerate(["units", "paren", "symbol", "punct"]):
            flags = {k: p[dim] for k, p in profiles.items()}
            if flags.get(ca) and sum(flags.values()) == 1:
                rep["M3"].append({"id": q["question_id"], "cue": name,
                                  "note": "only correct option carries this cue"})

    # M1 longest-correct + M2 position (report-only, mcsc)
    longest = []
    for q in mcsc:
        opts = q.get("options") or {}
        lens = {k: norm_len(v) for k, v in opts.items()}
        ca = str(q.get("correct_answer"))
        if lens and ca in lens and lens[ca] == max(lens.values()) and \
                list(lens.values()).count(max(lens.values())) == 1:
            longest.append(q["question_id"])
    frac = len(longest) / max(1, len(mcsc))
    rep["M1"].append({"batch_longest_correct_pct": round(frac * 100, 1),
                      "tolerance_pct": LONGEST_TOLERANCE * 100,
                      "ids": longest if frac > LONGEST_TOLERANCE else "within tolerance"})
    hist = {}
    for q in mcsc:
        hist[str(q.get("correct_answer"))] = hist.get(str(q.get("correct_answer")), 0) + 1
    rep["M2"].append({"histogram": hist, "note": "balanced by imat_shuffle_options"})

    # M5 near-dup prompts across different sets
    for i in range(len(qs)):
        for j in range(i + 1, len(qs)):
            if qs[i].get("set_id") == qs[j].get("set_id"):
                continue
            if jaccard(body_text(qs[i]), body_text(qs[j])) > JACCARD_DUP:
                rep["M5"].append({"pair": [qs[i]["question_id"], qs[j]["question_id"]],
                                  "flag_for_regen": qs[j]["question_id"]})

    # M7 ratio
    for q in qs:
        te, ta, dr = q.get("t_expert_sec"), q.get("t_average_sec"), q.get("discrimination_ratio")
        issues = []
        if te and ta and ta <= te:
            issues.append("t_average <= t_expert")
        if dr is not None and not (RATIO_LOW <= dr <= RATIO_HIGH):
            issues.append(f"DR {dr} out of [{RATIO_LOW},{RATIO_HIGH}]")
        if issues:
            rep["M7"].append({"id": q["question_id"], "issues": issues})

    # M8 verification syntax
    for q in qs:
        expr = (q.get("verification") or {}).get("expr", "")
        if not expr:
            continue
        for seg in [s.strip() for s in expr.split(";") if s.strip()]:
            if seg.startswith(("import ", "from ")):
                continue
            try:
                compile(seg, "<string>", "single")
            except SyntaxError as e:
                rep["M8"].append({"id": q["question_id"], "seg": seg, "err": str(e)})

    # M9 expected vs answer
    for q in qs:
        v = q.get("verification") or {}
        expected = str(v.get("expected", "")).strip()
        if not expected:
            continue
        target = (str(q.get("correct_answer", "")).strip() if q["question_type"] == "mcsc"
                  else str(q.get("tita_answer", "")).strip())
        if expected != target:
            rep["M9"].append({"id": q["question_id"], "expected": expected,
                              "answer": target})

    # M10 set integrity
    sets = {}
    for q in qs:
        if q.get("shared_set"):
            sets.setdefault(q["set_id"], []).append(q)
    for sid, members in sets.items():
        members.sort(key=lambda x: x["question_id"])
        mids = [m["question_id"] for m in members]
        problems = []
        if mids != list(range(mids[0], mids[0] + len(mids))):
            problems.append("non-contiguous ids")
        if [m["set_seq"] for m in members] != list(range(1, len(members) + 1)):
            problems.append("set_seq not 1..n")
        keys = {json.dumps(m.get("stimulus") or {}, sort_keys=True) for m in members}
        if len(keys) != 1:
            problems.append("stimulus differs across set")
        if problems:
            rep["M10"].append({"set_id": sid, "problems": problems})

    # M11 length-bias: the correct option must NOT be noticeably the longest
    # (students game AI papers by picking the longest option). Flag any item
    # where the key is the strict max and exceeds the 2nd-longest by >margin,
    # plus a batch cap on how often the key is the longest at all.
    longest_key = 0
    for q in mcsc:
        opts = q.get("options") or {}
        ca = str(q.get("correct_answer"))
        if ca not in opts:
            continue
        lens = {k: norm_len(v) for k, v in opts.items()}
        cl = lens[ca]
        others = [v for k, v in lens.items() if k != ca]
        mx = max(others) if others else 0
        if cl >= max(lens.values()) and list(lens.values()).count(max(lens.values())) == 1:
            longest_key += 1
        if cl > mx and (cl - mx) > LEN_BIAS_MARGIN * max(cl, 1) and (cl - mx) >= LEN_BIAS_MIN_ABS:
            rep["M11"].append({"id": q["question_id"], "issue": "correct option is "
                               "noticeably the longest", "correct_len": cl,
                               "max_distractor_len": mx})
    batch_frac = longest_key / max(1, len(mcsc))
    rep["M11"].append({"batch_correct_is_longest_pct": round(batch_frac * 100, 1),
                       "cap_pct": LEN_BATCH_CAP * 100,
                       "over_cap": batch_frac > LEN_BATCH_CAP})

    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/imat/questions.json")
    ap.add_argument("--report", default="work/imat/mech_report.json")
    ap.add_argument("--no-fix", action="store_true")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)
    rep = check(qs, fix=not args.no_fix)
    if not args.no_fix:
        with open(args.inp, "w", encoding="utf-8") as f:
            json.dump(qs, f, indent=2, ensure_ascii=False)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=2, ensure_ascii=False)

    m11_q = [x for x in rep["M11"] if "id" in x]
    m11_batch_over = any(x.get("over_cap") for x in rep["M11"])
    blocking = (len(rep["M3"]) + len(rep["M4"]) + len(rep["M5"]) +
                sum(1 for x in rep["M6"] if not x.get("fixed")) +
                len(rep["M7"]) + len(rep["M8"]) + len(rep["M9"]) + len(rep["M10"]) +
                len(m11_q) + (1 if m11_batch_over else 0))
    print(f"[OK] IMAT mechanical report -> {args.report}")
    for k in ("M1", "M2"):
        print(f"   {k}: {rep[k][-1] if rep[k] else 'n/a'}")
    for k in ("M3", "M4", "M5", "M6", "M7", "M8", "M9", "M10"):
        print(f"   {k}: {len(rep[k])}")
    print(f"   M11 length-bias: {len(m11_q)} flagged, {rep['M11'][-1]}")
    print(f"   BLOCKING (need attention): {blocking}")


if __name__ == "__main__":
    main()
