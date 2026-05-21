#!/usr/bin/env python3
"""selftest.py — prove the deterministic scripts run without the model.

Builds a tiny 4-question fixture, runs the full deterministic chain
(compute_ratios -> recompute_answers -> mechanical_checks -> export_csv ->
export_md) in a temp area, and asserts the outputs exist and are well-formed.

Run from the repo root:
    python scripts/selftest.py
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)
    print("$", " ".join(os.path.basename(a) if a.endswith(".py") else a for a in args))
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip())
    return r.returncode


def main():
    tmp = tempfile.mkdtemp(prefix="qgen_selftest_")
    qpath = os.path.join(tmp, "questions.json")
    fixture = [
        {
            "question_id": 1, "question_type": "mcsc", "content_type": "text",
            "question_text": "A pen costs ₹15 and sells for ₹18. Profit %?",
            "options": {"1": "15%", "2": "18%", "3": "20%", "4": "25%"},
            "correct_answer": "3",
            "explanation": "Profit 3 on CP 15 = 20%. Distractors map to wrong-base errors.",
            "difficulty": 0, "t_expert_sec": 8, "t_average_sec": 40,
            "topic": "Arithmetic",
            "verification": {"expr": "'3' if round((18-15)/15*100)==20 else '0'", "expected": "3"},
        },
        {
            "question_id": 2, "question_type": "mcsc", "content_type": "text",
            "question_text": "Largest angle when angles are 2:3:4?",
            "options": {"1": "60", "2": "80", "3": "90", "4": "100"},
            "correct_answer": "2",
            "explanation": "9x=180 -> x=20 -> 4x=80. Distractors: 3x, right-angle assumption.",
            "difficulty": 0, "t_expert_sec": 8, "t_average_sec": 45,
            "topic": "Geometry",
            "verification": {"expr": "x=180/9; '2' if 4*x==80 else '0'", "expected": "2"},
        },
        {
            "question_id": 3, "question_type": "mcsc", "content_type": "markdown",
            "question_text": "Remainder of $7^{100}$ mod 48?",
            "options": {"1": "7", "2": "1", "3": "43", "4": "25"},
            "correct_answer": "2",
            "explanation": "7^2=49≡1, so 7^100≡1. Distractors: 7^1, sign error.",
            "difficulty": 1, "t_expert_sec": 22, "t_average_sec": 180,
            "topic": "Number Theory",
            "verification": {"expr": "'2' if pow(7,100,48)==1 else '0'", "expected": "2"},
        },
        {
            "question_id": 4, "question_type": "mcsc", "content_type": "text",
            "question_text": "P(exactly 3 heads in 5 fair tosses)?",
            "options": {"1": "1/4", "2": "5/16", "3": "3/8", "4": "5/32"},
            "correct_answer": "2",
            "explanation": "C(5,3)/32 = 10/32 = 5/16. Distractors: wrong denom, wrong choose.",
            "difficulty": 1, "t_expert_sec": 20, "t_average_sec": 160,
            "topic": "Probability",
            "verification": {"expr": "'2' if comb(5,3)/2**5==5/16 else '0'", "expected": "2"},
        },
    ]
    with open(qpath, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)

    csv_out = os.path.join(tmp, "paper.csv")
    md_out = os.path.join(tmp, "key.md")

    rc = 0
    rc |= run("scripts/compute_ratios.py", "--in", qpath)
    rc |= run("scripts/recompute_answers.py", "--in", qpath, "--report", os.path.join(tmp, "rc.json"))
    rc |= run("scripts/mechanical_checks.py", "--in", qpath, "--report", os.path.join(tmp, "mech.json"))
    rc |= run("scripts/export_csv.py", "--in", qpath, "--out", csv_out)
    rc |= run("scripts/export_md.py", "--in", qpath, "--out", md_out, "--title", "Selftest")

    # assertions
    assert os.path.exists(csv_out), "CSV not written"
    assert os.path.exists(md_out), "MD not written"
    with open(csv_out, encoding="utf-8") as f:
        header = f.readline().strip()
    assert header.startswith("questionType,contentType,contentBody"), "bad CSV header"
    with open(qpath, encoding="utf-8") as f:
        data = json.load(f)
    assert all("discrimination_ratio" in q for q in data), "ratio not computed"
    with open(os.path.join(tmp, "rc.json"), encoding="utf-8") as f:
        rcrep = json.load(f)
    assert all(r["verdict"] == "MATCH" for r in rcrep), "recompute found a mismatch in fixture"

    print("\n[PASS] selftest OK — all scripts ran, outputs well-formed.")
    print(f"       fixture dir: {tmp}")
    sys.exit(0 if rc == 0 else 1)


if __name__ == "__main__":
    main()
