#!/usr/bin/env python3
"""generate_run_report.py — Deterministic run report writer.

Reads all intermediate artefacts and writes output/run_report.md.
The LLM orchestrator must NOT write this file — call this script instead.

Usage:
    python scripts/generate_run_report.py \
        --command work/command.json \
        --questions work/questions.json \
        --mech-report work/mech_report.json \
        --qc-report work/qc_report.json \
        --recompute-report work/recompute_report.json \
        --out output/run_report.md \
        --mech-cycles 2 --qc-cycles 2 --remech-cycles 1 \
        [--unresolved output/unresolved_report.md]
"""
import argparse
import json
import os
from collections import Counter
from datetime import date


def load(path: str) -> dict | list | None:
    if not path or not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--command",    default="work/command.json")
    ap.add_argument("--questions",  default="work/questions.json")
    ap.add_argument("--mech-report",    dest="mech",    default="work/mech_report.json")
    ap.add_argument("--qc-report",      dest="qc",      default="work/qc_report.json")
    ap.add_argument("--recompute-report", dest="recompute", default="work/recompute_report.json")
    ap.add_argument("--out", default="output/run_report.md")
    ap.add_argument("--mech-cycles",   dest="mech_cycles",   type=int, default=0)
    ap.add_argument("--qc-cycles",     dest="qc_cycles",     type=int, default=0)
    ap.add_argument("--remech-cycles", dest="remech_cycles", type=int, default=0)
    ap.add_argument("--unresolved", default=None)
    args = ap.parse_args()

    cmd  = load(args.command)   or {}
    qs   = load(args.questions) or []
    mech = load(args.mech)      or {}
    qc   = load(args.qc)        or []
    rcp  = load(args.recompute) or []

    n = len(qs)

    # ── Plan vs requested ────────────────────────────────────────────────
    diff_req = cmd.get("difficulty_ratio", {})
    diff_got = Counter(str(q.get("difficulty")) for q in qs)

    # ── Answer position histogram ─────────────────────────────────────────
    pos_hist = Counter(int(q["correct_answer"]) for q in qs
                       if str(q.get("correct_answer")) in {"1","2","3","4"})
    longest_pct = max(pos_hist.values(), default=0) / max(n, 1) * 100

    # ── Discrimination ratio stats ────────────────────────────────────────
    dr_bands: dict[str, list[float]] = {}
    for q in qs:
        band = str(q.get("difficulty", "?"))
        dr = q.get("discrimination_ratio")
        if dr is not None:
            dr_bands.setdefault(band, []).append(float(dr))

    def dr_row(band: str) -> str:
        vals = dr_bands.get(band, [])
        if not vals:
            return "—"
        return f"min={min(vals):.1f}  max={max(vals):.1f}  mean={sum(vals)/len(vals):.1f}"

    # ── Mechanical check summary ──────────────────────────────────────────
    mech_lines = []
    for key in ("M1","M2","M3","M4","M5","M6","M7","M8","M9"):
        items = mech.get(key, [])
        if items:
            mech_lines.append(f"- {key}: {len(items)} item(s)")

    # ── QC summary ────────────────────────────────────────────────────────
    qc_pass  = sum(1 for v in qc if v.get("verdict") == "PASS")
    qc_fix   = sum(1 for v in qc if v.get("action")  == "fix_in_place")
    qc_route = sum(1 for v in qc if v.get("action")  == "route_to_creator")

    # ── Recompute summary ─────────────────────────────────────────────────
    rcp_counts = Counter(r.get("verdict") for r in rcp)

    # ── Unresolved ────────────────────────────────────────────────────────
    unresolved_note = ""
    if args.unresolved and os.path.exists(args.unresolved):
        unresolved_note = f"\nSee [{args.unresolved}]({args.unresolved}) for unresolved items.\n"

    # ── Build report ─────────────────────────────────────────────────────
    lines = [
        f"# Run Report — CAT-Level MCQ Paper",
        f"",
        f"**Generated:** {date.today()}  ",
        f"**Command:** `--count {cmd.get('count','?')} "
        f"--difficulty \"{', '.join(f'{k}:{v}' for k,v in cmd.get('difficulty_ratio',{}).items())}\" "
        f"--notes \"{cmd.get('notes','')}\" "
        f"--id-start {cmd.get('id_start','?')}`",
        f"",
        f"---",
        f"",
        f"## Plan vs Requested",
        f"",
        f"| Metric | Requested | Delivered |",
        f"|--------|-----------|-----------|",
        f"| Total questions | {cmd.get('count','?')} | {n} |",
    ]
    for lvl in sorted(diff_req.keys(), key=lambda x: float(x)):
        label = {0: "Easy (0)", 0.5: "Medium (0.5)", 1: "Hard (1)"}.get(float(lvl), lvl)
        lines.append(f"| {label} | {diff_req[lvl]} | {diff_got.get(str(lvl), 0)} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## Phase Cycle Counts",
        f"",
        f"| Phase | Cycles Used | Cap |",
        f"|-------|-------------|-----|",
        f"| Phase 3 — Mechanical checks | {args.mech_cycles} | 3 |",
        f"| Phase 4 — Semantic QC       | {args.qc_cycles}  | 3 |",
        f"| Phase 5 — Re-mechanical     | {args.remech_cycles} | 2 |",
        f"",
        f"---",
        f"",
        f"## Mechanical Check Summary",
        f"",
    ]
    if mech_lines:
        lines += mech_lines
    else:
        lines.append("All mechanical checks clean on final pass.")

    lines += [
        f"",
        f"---",
        f"",
        f"## Semantic QC Summary",
        f"",
        f"### Recompute verdicts",
        f"",
        f"| Verdict | Count |",
        f"|---------|-------|",
    ]
    for verdict in ("MATCH", "MISMATCH", "ERROR", "UNCHECKABLE"):
        c = rcp_counts.get(verdict, 0)
        if c:
            lines.append(f"| {verdict} | {c} |")

    lines += [
        f"",
        f"### QC reviewer",
        f"",
        f"| Action | Count |",
        f"|--------|-------|",
        f"| PASS (clean) | {qc_pass} |",
        f"| fix_in_place | {qc_fix} |",
        f"| route_to_creator | {qc_route} |",
        f"",
        f"---",
        f"",
        f"## Answer-Position Histogram",
        f"",
        f"| Position | Count | % |",
        f"|----------|-------|---|",
    ]
    for p in range(1, 5):
        c = pos_hist.get(p, 0)
        lines.append(f"| {p} | {c} | {c/max(n,1)*100:.1f}% |")

    lines += [
        f"",
        f"Longest-correct: **{longest_pct:.1f}%**",
        f"",
        f"---",
        f"",
        f"## Discrimination Ratio Summary",
        f"",
        f"| Band | Min | Max | Mean | Target |",
        f"|------|-----|-----|------|--------|",
        f"| Easy (0)      | {dr_row('0')}   | 4–6   |",
        f"| Medium (0.5)  | {dr_row('0.5')} | 6–7.5 |",
        f"| Hard (1)      | {dr_row('1')}   | 7.5–9 |",
        f"",
        f"---",
        f"",
        f"## Output Files",
        f"",
        f"| File | Description |",
        f"|------|-------------|",
        f"| `output/paper.csv` | Platform CSV, {n} rows |",
        f"| `output/paper_answer_key.md` | Answer key with full solutions |",
        f"| `work/questions.json` | Full question set with all metadata |",
        f"| `work/qc_report.json` | Final QC verdicts |",
        f"| `work/recompute_report.json` | Answer verification report |",
    ]

    has_unresolved = args.unresolved and os.path.exists(args.unresolved)
    lines.append(f"")
    lines.append(f"**Unresolved items:** {'See unresolved_report.md' if has_unresolved else 'None.'}")
    if unresolved_note:
        lines.append(unresolved_note)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"[OK] run report -> {args.out}")


if __name__ == "__main__":
    main()
