#!/usr/bin/env python3
"""validate_csv.py — Post-export CSV sanity check.

Verifies:
  V1 Header row matches the exact expected column order
  V2 Row count equals the number of questions in questions.json
  V3 No row has more columns than the header

Run after export_csv.py. Hard-stops on any failure.

Usage:
    python scripts/validate_csv.py --csv output/paper.csv \
        --questions work/questions.json
"""
import argparse
import csv
import json
import sys

EXPECTED_HEADER = [
    "questionType", "contentType", "contentBody", "intAnswer",
    "prepTime(in_seconds)", "floatAnswer.max", "floatAnswer.min",
    "fitbAnswer", "mcscAnswer", "subjectiveAnswer",
    "option.1", "option.2", "option.3", "option.4",
    "mcmcAnswer", "tagRelationships", "difficultyLevel",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="output/paper.csv")
    ap.add_argument("--questions", default="work/questions.json")
    args = ap.parse_args()

    with open(args.questions, encoding="utf-8") as f:
        qs = json.load(f)
    expected_rows = len(qs)

    errors = []

    with open(args.csv, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        errors.append("CSV is empty")
    else:
        header = rows[0]
        # V1 header
        # Allow extra columns appended after the standard ones
        if header[: len(EXPECTED_HEADER)] != EXPECTED_HEADER:
            errors.append(
                f"header mismatch\n"
                f"  expected: {EXPECTED_HEADER}\n"
                f"  got:      {header[: len(EXPECTED_HEADER)]}"
            )

        data_rows = rows[1:]

        # V2 row count
        if len(data_rows) != expected_rows:
            errors.append(
                f"row count mismatch: CSV has {len(data_rows)} data rows, "
                f"questions.json has {expected_rows}"
            )

        # V3 column count consistency
        n_cols = len(header)
        bad = [i + 2 for i, r in enumerate(data_rows) if len(r) != n_cols]
        if bad:
            errors.append(f"rows with wrong column count (line numbers): {bad[:10]}")

    if errors:
        print("[FAIL] CSV validation errors:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    print(f"[OK] CSV valid: {expected_rows} data rows, "
          f"{len(rows[0])} columns -> {args.csv}")


if __name__ == "__main__":
    main()
