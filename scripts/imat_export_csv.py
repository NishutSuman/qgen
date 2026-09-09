#!/usr/bin/env python3
"""imat_export_csv.py — IMAT platform CSV.

One row per question. The stimulus is composed into contentBody for every
question (self-contained). Extra leading columns (section, setId, setSeq) let
you build the set-mode configs: questions sharing a setId go into ONE config,
in seq order, in consecutive configs.

Header:
  section, setId, setSeq, questionType, contentType, contentBody, intAnswer,
  prepTime(in_seconds), floatAnswer.max, floatAnswer.min, fitbAnswer,
  mcscAnswer, subjectiveAnswer, option.1..option.5, mcmcAnswer,
  tagRelationships, difficultyLevel

NOTE: option.5 is included for 5-option items (odd-one-out). TITA numeric goes
to intAnswer (integer) else fitbAnswer. Adjust mapping here if the platform
import spec differs — this is the single place that owns it.

Usage:
    python scripts/imat_export_csv.py --in work/imat/questions.json \
        --out output/imat_paper.csv
"""
import argparse
import csv
import json

from imat_render import (answer_fields, compose_body, diff_label, is_markdown,
                         option_cells)

HEADER = [
    "section", "setId", "setSeq", "questionType", "contentType", "contentBody",
    "intAnswer", "prepTime(in_seconds)", "floatAnswer.max", "floatAnswer.min",
    "fitbAnswer", "mcscAnswer", "subjectiveAnswer",
    "option.1", "option.2", "option.3", "option.4", "option.5",
    "mcmcAnswer", "tagRelationships", "difficultyLevel",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/imat/questions.json")
    ap.add_argument("--out", default="output/imat_paper.csv")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    # Guard against cross-pipeline confusion: IMAT records carry 'section'.
    if qs and not all("section" in q for q in qs):
        raise SystemExit("[FAIL] input is not IMAT data (no 'section'). "
                         "Use scripts/export_csv.py for the normal mcsc flow.")

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(HEADER)
        for q in qs:
            body = compose_body(q)
            mcsc, int_ans, fitb = answer_fields(q)
            o1, o2, o3, o4, o5 = option_cells(q)
            # VARC/DILR carry passages, tables and structured prompts: always
            # markdown so paragraph breaks (\n\n) and **bold** render on-platform.
            ctype = "markdown" if (q.get("section") in ("VARC", "DILR")
                                   or is_markdown(body)) else "text"
            w.writerow([
                q.get("section", ""), q.get("set_id", ""), q.get("set_seq", ""),
                q.get("question_type", ""), ctype, body,
                int_ans, q.get("t_average_sec", ""), "", "", fitb,
                mcsc, "", o1, o2, o3, o4, o5, "",
                q.get("topic", ""), diff_label(q.get("difficulty", "")),
            ])
    print(f"[OK] wrote {len(qs)} IMAT rows -> {args.out}")


if __name__ == "__main__":
    main()
