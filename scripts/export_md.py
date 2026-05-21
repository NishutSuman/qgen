#!/usr/bin/env python3
"""export_md.py — Phase 6 deliverable.

Exam-style Markdown with the correct option marked and the full solution shown.

Usage:
    python scripts/export_md.py --in work/questions.json \
        --out output/paper_answer_key.md --title "Qualifier Test"
"""
import argparse
import json

DIFF_LABEL = {0: "Easy", 0.5: "Medium", 1: "Hard",
              "0": "Easy", "0.5": "Medium", "1": "Hard"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/questions.json")
    ap.add_argument("--out", default="output/paper_answer_key.md")
    ap.add_argument("--title", default="Question Paper — Answer Key")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)

    lines = [f"# {args.title}", ""]
    # quick summary
    hist = {}
    for q in qs:
        hist[str(q.get("difficulty"))] = hist.get(str(q.get("difficulty")), 0) + 1
    lines.append(f"_Total: {len(qs)} questions · "
                 f"Easy {hist.get('0',0)} / Medium {hist.get('0.5',0)} / Hard {hist.get('1',0)}_")
    lines.append("")
    lines.append("---")
    lines.append("")

    for q in qs:
        diff = DIFF_LABEL.get(q.get("difficulty"), q.get("difficulty"))
        te = q.get("t_expert_sec", "?")
        ta = q.get("t_average_sec", "?")
        dr = q.get("discrimination_ratio", "?")
        ca = str(q.get("correct_answer"))

        lines.append(
            f"**Q{q['question_id']}.** *(Difficulty: {diff} · "
            f"Expert {te}s / Avg {ta}s · DR {dr})*"
        )
        lines.append("")
        lines.append(q.get("question_text", ""))
        lines.append("")
        for i in range(1, 5):
            opt = q.get("options", {}).get(str(i), "")
            mark = "✅ " if str(i) == ca else ""
            lines.append(f"- {mark}({i}) {opt}")
        lines.append("")
        correct_text = q.get("options", {}).get(ca, "")
        lines.append(f"**Answer: ({ca}) {correct_text}**")
        if q.get("explanation"):
            lines.append("")
            lines.append(f"**Solution:** {q['explanation']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[OK] wrote answer key ({len(qs)} questions) -> {args.out}")


if __name__ == "__main__":
    main()
