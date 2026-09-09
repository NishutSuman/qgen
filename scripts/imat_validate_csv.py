#!/usr/bin/env python3
"""imat_validate_csv.py — IMAT CSV ↔ source parity (HARD STOP).

The verification PDF and the upload CSV are both generated from
work/imat/questions.json. This check proves the CSV faithfully reflects that
source, so verifying the PDF == verifying the upload:
  V1 header matches the IMAT header exactly
  V2 one data row per question, in question_id order
  V3 each row's contentBody == compose_body(question)
  V4 each row's answer (mcscAnswer / intAnswer / fitbAnswer) == the source answer

Usage:
    python scripts/imat_validate_csv.py --csv output/imat_paper.csv \
        --questions work/imat/questions.json
"""
import argparse
import csv
import json
import sys

from imat_render import answer_fields, compose_body
from imat_export_csv import HEADER


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="output/imat_paper.csv")
    ap.add_argument("--questions", default="work/imat/questions.json")
    args = ap.parse_args()

    with open(args.questions, encoding="utf-8") as f:
        qs = json.load(f)
    with open(args.csv, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))

    errors = []
    if not rows:
        sys.exit("[FAIL] CSV empty")
    if rows[0] != HEADER:
        errors.append(f"header mismatch\n  expected: {HEADER}\n  got:      {rows[0]}")
    data = rows[1:]
    if len(data) != len(qs):
        errors.append(f"row count {len(data)} != questions {len(qs)}")

    col = {h: i for i, h in enumerate(HEADER)}
    for idx, (row, q) in enumerate(zip(data, qs), start=1):
        if len(row) != len(HEADER):
            errors.append(f"row {idx}: wrong column count")
            continue
        if row[col["contentBody"]] != compose_body(q):
            errors.append(f"row {idx} (Q{q['question_id']}): contentBody mismatch")
        mcsc, int_ans, fitb = answer_fields(q)
        if (row[col["mcscAnswer"]], row[col["intAnswer"]], row[col["fitbAnswer"]]) != \
                (mcsc, int_ans, fitb):
            errors.append(f"row {idx} (Q{q['question_id']}): answer mismatch")

    if errors:
        print("[FAIL] IMAT CSV parity errors:")
        for e in errors[:20]:
            print("  -", e)
        sys.exit(1)
    print(f"[OK] IMAT CSV parity: {len(data)} rows match source -> {args.csv}")


if __name__ == "__main__":
    main()
