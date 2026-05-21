#!/usr/bin/env python3
"""export_csv.py — Phase 6 deliverable.

Writes the platform CSV with the exact header. Any extra/unknown columns passed
via --extra-cols are appended at the END and left blank (never removed).

Header (verbatim):
questionType,contentType,contentBody,intAnswer,prepTime(in_seconds),
floatAnswer.max,floatAnswer.min,fitbAnswer,mcscAnswer,subjectiveAnswer,
option.1,option.2,option.3,option.4,mcmcAnswer,tagRelationships,difficultyLevel

Usage:
    python scripts/export_csv.py --in work/questions.json --out output/paper.csv
    # optional: --extra-cols "sourceId,reviewerNote"
"""
import argparse
import csv
import json

BASE_HEADER = [
    "questionType", "contentType", "contentBody", "intAnswer",
    "prepTime(in_seconds)", "floatAnswer.max", "floatAnswer.min", "fitbAnswer",
    "mcscAnswer", "subjectiveAnswer", "option.1", "option.2", "option.3",
    "option.4", "mcmcAnswer", "tagRelationships", "difficultyLevel",
]


def fmt_diff(d):
    # keep 0, 0.5, 1 clean (no trailing .0 on integers)
    if d in (0, 1) or d in ("0", "1"):
        return str(int(float(d)))
    return str(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/questions.json")
    ap.add_argument("--out", default="output/paper.csv")
    ap.add_argument("--extra-cols", default="",
                    help="comma-separated extra column names appended at the end (blank cells)")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    extra = [c.strip() for c in args.extra_cols.split(",") if c.strip()]
    header = BASE_HEADER + extra

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(header)
        for q in qs:
            opts = q.get("options", {})
            row = [
                "mcsc",                                  # questionType
                q.get("content_type", "text"),           # contentType
                q.get("question_text", ""),              # contentBody
                "",                                      # intAnswer
                q.get("t_average_sec", ""),              # prepTime(in_seconds)
                "",                                      # floatAnswer.max
                "",                                      # floatAnswer.min
                "",                                      # fitbAnswer
                q.get("correct_answer", ""),             # mcscAnswer
                "",                                      # subjectiveAnswer
                opts.get("1", ""),                       # option.1
                opts.get("2", ""),                       # option.2
                opts.get("3", ""),                       # option.3
                opts.get("4", ""),                       # option.4
                "",                                      # mcmcAnswer
                q.get("topic", ""),                      # tagRelationships
                fmt_diff(q.get("difficulty", "")),       # difficultyLevel
            ]
            row += [""] * len(extra)                     # extra cols blank
            w.writerow(row)

    print(f"[OK] wrote {len(qs)} rows -> {args.out}")
    if extra:
        print(f"   appended extra columns (blank): {extra}")


if __name__ == "__main__":
    main()
