#!/usr/bin/env python3
"""imat_selftest.py — prove the IMAT deterministic chain runs without the model.

Run with the project venv (matplotlib needed for charts + PDF):
    .venv/bin/python scripts/imat_selftest.py

Covers: plan chain for both variants (incl. ±5% bounds), then a tiny post-create
fixture (RC set, odd-one-out 5-option, DI table set, DI graph set, QA mcsc, QA
tita) through compute_ratios -> recompute -> mechanical -> shuffle -> charts ->
export csv/pdf -> CSV parity -> bank add/check.
"""
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(*args, expect=0):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)
    name = " ".join(os.path.basename(a) if a.endswith(".py") else a for a in args)
    print("$", name)
    if r.stdout.strip():
        print(r.stdout.strip())
    if r.returncode != expect:
        print("STDERR:", r.stderr.strip())
        raise SystemExit(f"[FAIL] '{name}' exit {r.returncode}, expected {expect}")
    return r


def main():
    tmp = tempfile.mkdtemp(prefix="imat_selftest_")
    work = os.path.join(tmp, "work"); os.makedirs(work)
    out = os.path.join(tmp, "out"); os.makedirs(out)

    # ---- plan chain (both variants + flex bounds) ----
    for paper, base in (("MBA", 68), ("BS", 66)):
        cmd = os.path.join(work, f"command_{paper}.json")
        plan = os.path.join(work, f"plan_{paper}.json")
        run("scripts/imat_validate_command.py", "--paper", paper, "--out", cmd)
        run("scripts/imat_plan.py", "--command", cmd, "--out", plan)
        run("scripts/imat_validate_plan.py", "--plan", plan, "--command", cmd)
        with open(plan, encoding="utf-8") as f:
            p = json.load(f)
        assert p["meta"]["count"] == base, f"{paper} count {p['meta']['count']} != {base}"
    # flex: within ±5% ok, outside fails
    run("scripts/imat_validate_command.py", "--paper", "MBA", "--count", "70",
        "--out", os.path.join(work, "c70.json"))
    run("scripts/imat_validate_command.py", "--paper", "MBA", "--count", "80",
        "--out", os.path.join(work, "c80.json"), expect=1)
    # TITA flex (4-8): --tita 7 ok and total stays 68 (MCQ pool compensates); --tita 9 fails
    ct = os.path.join(work, "tita7.json")
    run("scripts/imat_validate_command.py", "--paper", "MBA", "--tita", "7", "--out", ct)
    pt = os.path.join(work, "plan_tita7.json")
    run("scripts/imat_plan.py", "--command", ct, "--out", pt)
    with open(pt, encoding="utf-8") as f:
        ptj = json.load(f)
    n_tita = sum(1 for q in ptj["questions"] if q["question_type"] == "tita")
    assert ptj["meta"]["count"] == 68 and n_tita == 7, f"tita-flex wrong: {ptj['meta']['count']}/{n_tita}"
    run("scripts/imat_validate_command.py", "--paper", "MBA", "--tita", "9",
        "--out", os.path.join(work, "tita9.json"), expect=1)
    # BS now allows a graph DI set (DILR-5)
    bsplan = json.load(open(os.path.join(work, "plan_BS.json"), encoding="utf-8"))
    assert any(q["kind"] == "graph" for q in bsplan["questions"]), "BS should allow a graph set"
    print("[ok] plan chain + count flex + TITA flex + BS-graph capability")

    # ---- post-create fixture ----
    rc_stim = {"kind": "passage", "markdown":
               "Exercise benefits the body and brain. Regular moderate activity "
               "improves health more through consistency than intensity."}
    table_stim = {"kind": "table", "markdown":
                  "Units Sold\n| Product | A | B |\n|---|--:|--:|\n| X | 10 | 20 |\n| Y | 30 | 40 |"}
    graph_stim = {"kind": "graph", "markdown": "Units sold per quarter ('000).",
                  "chart": [{"type": "grouped_bar", "title": "Units Sold (in '000)",
                             "y_label": "Units ('000)", "categories": ["ProBook", "ZenBook"],
                             "series": {"Q1": [4, 3], "Q2": [5, 2.5], "Q3": [6, 4.5]}}]}

    def mc(qid, section, set_id, seq, size, shared, kind, nopt, diff, qtext,
           opts, expl, te, ta, stim=None, expr=None, topic="t"):
        q = {"question_id": qid, "section": section, "set_id": set_id, "set_seq": seq,
             "set_size": size, "shared_set": shared, "kind": kind, "question_type": "mcsc",
             "num_options": nopt, "topic": topic, "difficulty": diff,
             "question_text": qtext, "options": opts, "correct_answer": "1",
             "explanation": expl, "t_expert_sec": te, "t_average_sec": ta}
        if stim:
            q["stimulus"] = stim
        if expr:
            q["verification"] = {"expr": expr, "expected": "1"}
        return q

    fixture = [
        mc(1, "VARC", "RC1", 1, 2, True, "passage", 4, 0.5,
           "What best captures the passage's main idea?",
           {"1": "Consistent moderate exercise yields broad health benefits",
            "2": "Exercise is useful only for steady long-term weight loss",
            "3": "Only well-trained athletes gain real health benefits here",
            "4": "The BDNF chemical alone explains every exercise benefit"},
           "The passage stresses consistency over intensity; distractors are narrow misreadings.",
           20, 90, stim=rc_stim),
        mc(2, "VARC", "RC1", 2, 2, True, "passage", 4, 0.5,
           "The author would most likely agree that:",
           {"1": "A previously inactive person can gain useful health improvement",
            "2": "Exercise has been proven to fully prevent all known disease",
            "3": "Rest days are never necessary for a committed exerciser",
            "4": "Training intensity always beats consistency for results"},
           "Inference matches the inactivity-to-active gain; others overstate or contradict.",
           22, 100, stim=rc_stim),
        mc(3, "VARC", "ODD-1", 1, 1, False, "none", 5, 0.5,
           "Sentences: 1 EVs are clean. 2 Subsidies encourage EVs. 3 Charging is "
           "limited. 4 Pasta has many shapes. 5 Batteries are improving. Odd one out?",
           {"1": "4", "2": "1", "3": "2", "4": "3", "5": "5"},
           "Sentence 4 about pasta is unrelated to the EV theme of the others.",
           25, 110),
        mc(4, "DILR", "DT1", 1, 2, True, "table", 4, 0.5,
           "What is the total units sold in Store A across both products?",
           {"1": "40", "2": "30", "3": "50", "4": "60"},
           "Store A: X=10 plus Y=30 gives 40; distractors mix up rows/columns.",
           30, 180, stim=table_stim, expr="'1' if 10+30==40 else '0'"),
        mc(5, "DILR", "DT1", 2, 2, True, "table", 4, 0.5,
           "What is the total units of Product X across stores A and B?",
           {"1": "30", "2": "40", "3": "50", "4": "70"},
           "Product X: A=10 plus B=20 gives 30; distractors add the wrong cells.",
           30, 175, stim=table_stim, expr="'1' if 10+20==30 else '0'"),
        mc(6, "DILR", "DG1", 1, 2, True, "graph", 4, 1,
           "What is ProBook's total units sold across Q1 to Q3?",
           {"1": "15", "2": "14", "3": "16", "4": "12"},
           "ProBook: 4 plus 5 plus 6 equals 15; distractors drop or misread a quarter.",
           35, 240, stim=graph_stim, expr="'1' if 4+5+6==15 else '0'"),
        mc(7, "DILR", "DG1", 2, 2, True, "graph", 4, 1,
           "Which is ProBook's highest single-quarter units figure?",
           {"1": "6", "2": "5", "3": "4", "4": "3"},
           "ProBook peaks at 6 in Q3; distractors are the other quarters' values.",
           30, 210, stim=graph_stim, expr="'1' if max([4,5,6])==6 else '0'"),
        mc(8, "QA", "QA-MCQ-1", 1, 1, False, "none", 4, 0.5,
           "An item bought for 15 sells for 18. Profit percent?",
           {"1": "20", "2": "18", "3": "25", "4": "15"},
           "Profit 3 on cost 15 is 20 percent; distractors use wrong base or raw diff.",
           12, 60, expr="'1' if round((18-15)/15*100)==20 else '0'"),
        {"question_id": 9, "section": "QA", "set_id": "QA-TITA-1", "set_seq": 1,
         "set_size": 1, "shared_set": False, "kind": "none", "question_type": "tita",
         "num_options": 0, "topic": "QA/quant", "difficulty": 0.5,
         "question_text": "The average of 5 consecutive even numbers is 28. The largest is?",
         "tita_answer": "32",
         "explanation": "The five consecutive even numbers are 24, 26, 28, 30, 32; the "
                        "middle term equals the average 28, so the largest is 32.",
         "t_expert_sec": 18, "t_average_sec": 90,
         "verification": {"expr": "avg=28; '32' if avg+4==32 else '0'", "expected": "32"}},
    ]
    qpath = os.path.join(work, "questions.json")
    with open(qpath, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)

    run("scripts/compute_ratios.py", "--in", qpath)
    rc = run("scripts/recompute_answers.py", "--in", qpath,
             "--report", os.path.join(work, "rc.json"))
    with open(os.path.join(work, "rc.json"), encoding="utf-8") as f:
        verdicts = {r["id"]: r["verdict"] for r in json.load(f)}
    for qid in (4, 5, 6, 7, 8, 9):
        assert verdicts[qid] == "MATCH", f"Q{qid} recompute {verdicts[qid]}"

    run("scripts/imat_mechanical_checks.py", "--in", qpath,
        "--report", os.path.join(work, "mech.json"))
    with open(os.path.join(work, "mech.json"), encoding="utf-8") as f:
        mech = json.load(f)
    blocking = (len(mech["M3"]) + len(mech["M4"]) + len(mech["M5"]) +
                sum(1 for x in mech["M6"] if not x.get("fixed")) +
                len(mech["M7"]) + len(mech["M8"]) + len(mech["M9"]) + len(mech["M10"]))
    assert blocking == 0, f"mechanical blocking issues: { {k:v for k,v in mech.items() if v} }"

    run("scripts/imat_shuffle_options.py", "--in", qpath, "--seed", "7")
    # post-shuffle recompute must STILL match (shuffle repoints verification expr)
    run("scripts/recompute_answers.py", "--in", qpath, "--report", os.path.join(work, "rc2.json"))
    with open(os.path.join(work, "rc2.json"), encoding="utf-8") as f:
        v2 = {r["id"]: r["verdict"] for r in json.load(f)}
    for qid in (4, 5, 6, 7, 8, 9):
        assert v2[qid] == "MATCH", f"Q{qid} post-shuffle recompute {v2[qid]} (expr not repointed)"
    run("scripts/imat_charts.py", "--in", qpath, "--assets", os.path.join(out, "imat_assets"))
    assert os.path.exists(os.path.join(out, "imat_assets", "DG1_0.png")), "chart png missing"

    # S3 upload (dry-run: compute URLs without hitting S3) -> image_urls attached
    run("scripts/imat_upload_assets.py", "--in", qpath, "--base", out,
        "--prefix", "imat", "--date", "2026-06-25", "--dry-run")
    with open(qpath, encoding="utf-8") as f:
        qd = json.load(f)
    dg = [q for q in qd if q["set_id"] == "DG1"]
    assert all((q.get("stimulus") or {}).get("image_urls") for q in dg), "S3 URLs not attached to set"
    assert len({tuple(q["stimulus"]["image_urls"]) for q in dg}) == 1, "set members got different URLs"

    csv_out = os.path.join(out, "imat_paper.csv")
    pdf_out = os.path.join(out, "imat_paper.pdf")
    run("scripts/imat_export_csv.py", "--in", qpath, "--out", csv_out)
    run("scripts/imat_export_pdf.py", "--in", qpath, "--out", pdf_out, "--title", "Selftest IMAT")
    run("scripts/imat_validate_csv.py", "--csv", csv_out, "--questions", qpath)
    assert os.path.getsize(pdf_out) > 1000, "PDF too small / not written"
    with open(csv_out, encoding="utf-8") as f:
        csv_text = f.read()
    assert "amazonaws.com" in csv_text, "CSV does not embed the S3 chart URL"

    # archive: dated folder with flattened assets (output/imat_real/<date>/ scheme)
    arch = os.path.join(out, "imat_real")
    run("scripts/archive_paper.py", "--dir", arch, "--prefix", "imat_selftest_",
        "--files", csv_out, pdf_out, "--assets-dir", os.path.join(out, "imat_assets"),
        "--flatten-assets", "--date", "2026-06-25")
    adir = os.path.join(arch, "2026-06-25")
    assert os.path.exists(os.path.join(adir, "imat_selftest_imat_paper.csv")), "archive csv missing"
    assert os.path.exists(os.path.join(adir, "DG1_0.png")), "flattened chart missing in archive"

    # bank round-trip on a separate IMAT bank
    bank = os.path.join(work, "imat_history.jsonl")
    brep = os.path.join(work, "bank.json")
    run("scripts/question_bank.py", "check", "--in", qpath, "--bank", bank, "--report", brep)
    with open(brep, encoding="utf-8") as f:
        assert json.load(f)["flagged_ids"] == [], "fresh IMAT bank flagged something"
    run("scripts/question_bank.py", "add", "--in", qpath, "--bank", bank)
    run("scripts/question_bank.py", "check", "--in", qpath, "--bank", bank, "--report", brep)
    with open(brep, encoding="utf-8") as f:
        assert len(json.load(f)["flagged_ids"]) == len(fixture), "re-check did not flag dupes"

    print("\n[PASS] imat selftest OK — full IMAT deterministic chain ran, CSV↔source "
          "parity held, charts + PDF produced.")
    print(f"       artifacts: {out}")


if __name__ == "__main__":
    main()
