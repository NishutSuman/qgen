---
description: Generate a CAT-level MCQ paper (plan -> parallel create+QC -> mechanical checks -> semantic QC -> re-check -> CSV + MD)
argument-hint: --count 50 --difficulty "0:8, 0.5:18, 1:24" --notes "scope/exclusions/style"
allowed-tools: Bash, Read, Write, Edit, Task
---

You are the **orchestrator**. Run the full pipeline below. All questions are
single-correct 4-option MCQs (`mcsc`). Never hand-verify what a script can
verify. Honor every hard stop.

Command arguments: $ARGUMENTS

## Phase 0 — Validate command (HARD STOP)
```
python scripts/validate_command.py --count <N> --difficulty "<ratio>" --notes "<notes>" --id-start <start> --out work/command.json
```
If it exits non-zero, STOP and report the mismatch. Do nothing else.

## Phase 1 — Central plan.json (HARD STOP gate)
Write `plan.json` yourself (intent only — `question_id, type:"mcsc", topic,
difficulty, target_discrimination_band`). Spread topics across families; no
family > ~20% unless notes say so. Reproduce the difficulty ratio EXACTLY.
Do NOT put timing fields here. Then:
```
python scripts/validate_plan.py --plan plan.json --command work/command.json
```
If it fails, fix plan.json and re-run. Only proceed when it passes.

## Phase 2 — Parallel create + self-QC (20 per agent)
Split plan into chunks of 20. For each chunk, launch a `creator` subagent via
the Task tool (they run concurrently). Each writes ONLY
`work/questions_chunk_<N>.json` and runs the question-qc skill on its own 20
before returning. Then merge, set content types, and compute ratios:
```
python scripts/merge_chunks.py --plan plan.json --out work/questions.json
python scripts/set_content_type.py --in work/questions.json
python scripts/compute_ratios.py --in work/questions.json
```

## Phase 3 — Mechanical checks (MAX 3 CYCLES)
```
python scripts/mechanical_checks.py --in work/questions.json --report work/mech_report.json
```
Read the report. Auto-fixes are already applied to the file. For BLOCKING items
(M3/M4/M5/M6-unfixed/M7) route the specific IDs to a `creator` subagent for
targeted regen, then re-run. Stop after 3 cycles; log leftovers to
`output/unresolved_report.md`.

## Phase 4 — Semantic QC (MAX 3 CYCLES)
```
python scripts/recompute_answers.py --in work/questions.json --report work/recompute_report.json
```
Launch a `qc-reviewer` subagent (fresh eyes) to run the question-qc skill across
all questions plus the recompute report. Fix MISMATCH/flagged questions, re-run.
Stop after 3 cycles; log leftovers to unresolved_report.md.

## Phase 5 — Re-run mechanical checks (MAX 2 CYCLES)
QC edits can re-introduce cues/imbalance. Re-run Phase 3's command, fix, stop
after 2 cycles.

## Phase 6 — Shuffle + Export + Validate
First shuffle options and balance answer positions (script owns this — do NOT do it manually):
```
python scripts/shuffle_options.py --in work/questions.json
```
Then export:
```
python scripts/export_csv.py --in work/questions.json --out output/paper.csv
python scripts/export_md.py  --in work/questions.json --out output/paper_answer_key.md --title "<paper title>"
```
Then validate the CSV:
```
python scripts/validate_csv.py --csv output/paper.csv --questions work/questions.json
```
If validate_csv exits non-zero, STOP and report.

## Final — Run report (script, not LLM)
Do NOT write run_report.md yourself. Call the script with the exact cycle counts
you tracked during the run:
```
python scripts/generate_run_report.py \
  --mech-cycles <N> --qc-cycles <N> --remech-cycles <N> \
  [--unresolved output/unresolved_report.md]
```
Ship: paper.csv, paper_answer_key.md, work/questions.json, run_report.md
(+ unresolved_report.md if any items were dropped).

**Hard stops:** Phase 3 = 3 cycles, Phase 4 = 3 cycles, Phase 5 = 2 cycles,
single-question regen = 2 attempts then drop to unresolved. The pipeline must
always terminate and export whatever passed.
