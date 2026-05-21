#!/usr/bin/env python3
"""set_content_type.py — Auto-detect and set content_type on every question.

Rules (applied to question_text + all 4 option values):
  - Any LaTeX delimiter or command  ($, \\frac, \\sqrt, \\times, \\div,
    \\cdot, ^{, _{, \\leq, \\geq, \\neq, \\pi, \\infty) → "markdown"
  - Otherwise → "text"

Run after merge_chunks, before Phase 3. The LLM must NOT set content_type;
this script owns that field entirely.

Usage:
    python scripts/set_content_type.py --in work/questions.json
"""
import argparse
import json
import re

# Any of these in the text signals math/markdown content
_MATH_RE = re.compile(
    r"\$"                   # $ delimiter
    r"|\\frac\b"
    r"|\\sqrt\b"
    r"|\\times\b"
    r"|\\div\b"
    r"|\\cdot\b"
    r"|\\leq\b"
    r"|\\geq\b"
    r"|\\neq\b"
    r"|\\pi\b"
    r"|\\infty\b"
    r"|\\pm\b"
    r"|\^{"                 # superscript block
    r"|_{"                  # subscript block
)


def needs_markdown(q: dict) -> bool:
    texts = [q.get("question_text", "")]
    texts += list((q.get("options") or {}).values())
    return any(_MATH_RE.search(t) for t in texts if t)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/questions.json")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    changed = 0
    for q in qs:
        want = "markdown" if needs_markdown(q) else "text"
        if q.get("content_type") != want:
            q["content_type"] = want
            changed += 1

    with open(args.inp, "w", encoding="utf-8") as f:
        json.dump(qs, f, indent=2, ensure_ascii=False)

    md_count = sum(1 for q in qs if q.get("content_type") == "markdown")
    print(f"[OK] content_type set on {len(qs)} questions "
          f"({md_count} markdown, {len(qs)-md_count} text, {changed} changed)"
          f" -> {args.inp}")


if __name__ == "__main__":
    main()
