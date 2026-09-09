---
description: Generate an IMAT (CAT-pattern) paper — MBA or BS variant — through the same qgen pipeline (plan -> parallel create+QC -> mechanical -> semantic QC -> re-check -> shuffle -> CSV + verification PDF)
argument-hint: --paper MBA|BS [--count N (±5% of base only)]
allowed-tools: Bash, Read, Write, Edit, Task
---

You are the **IMAT orchestrator**. Build a full CAT-pattern paper (sections
VARC, DILR, QA) for the chosen variant, running the SAME pipeline shape as
`generate-questions`, but with the `imat_*` scripts and a SEPARATE question bank.
Use `.venv/bin/python` for every command below (matplotlib lives in the venv).
Honor every hard stop.

Command arguments: $ARGUMENTS

Key rules (do not violate):
- `--paper` is MBA or BS; it fixes structure AND difficulty. There is no
  `--difficulty` knob. `--count` is optional and may differ from the variant
  base by at most ±5% (absorbed by the QA MCQ flex pool). Patterns are fixed.
- Every question in a SET (RC passage, DI table, DI graph) must embed the FULL
  stimulus in its own `stimulus` field — identical across the set — because each
  question is uploaded separately and must stand alone.
- TITA questions are numeric type-in (no options). All others are `mcsc`
  (4 options; odd-one-out is 5).
- Scripts own everything mechanical (content_type, ratios, balancing, dedup,
  charts, CSV, PDF, reports). Never hand-do those.

## Phase 0 — Validate command (HARD STOP)
```
.venv/bin/python scripts/imat_validate_command.py --paper <MBA|BS> [--count <N>] --out work/imat/command.json
```

## Phase 1 — Plan + validate (HARD STOP gate)
The plan is mechanical from the blueprint (not hand-authored):
```
.venv/bin/python scripts/imat_plan.py --command work/imat/command.json --out work/imat/plan.json
.venv/bin/python scripts/imat_validate_plan.py --plan work/imat/plan.json --command work/imat/command.json
```

## Phase 2 — Parallel create + self-QC (per set / per chunk)
Build the cross-run avoid-list from the IMAT bank:
```
.venv/bin/python scripts/question_bank.py digest --bank bank/imat_history.jsonl --out work/imat/bank_recent.json
```
Group the plan into work units — keep each SHARED SET whole in one unit (never
split a passage/table/graph set across agents); batch singletons up to ~20.
Launch `creator-imat` subagents (Task tool, concurrent). Each reads its plan
slots + `work/command.json`-style notes + `work/imat/bank_recent.json`, follows
`.claude/skills/imat-question-creation/SKILL.md`, and writes ONLY its own
`work/imat/questions_chunk_<N>.json`. Then:
```
.venv/bin/python scripts/imat_merge_chunks.py --plan work/imat/plan.json --out work/imat/questions.json
.venv/bin/python scripts/set_content_type.py --in work/imat/questions.json
.venv/bin/python scripts/compute_ratios.py --in work/imat/questions.json
.venv/bin/python scripts/question_bank.py check --in work/imat/questions.json --bank bank/imat_history.jsonl --report work/imat/bank_report.json
```
Cross-run duplicates → route those IDs to a `creator-imat` for regen (MAX 2
attempts), re-run digest+check, then log leftovers to
`output/imat_unresolved_report.md`.

## Phase 3 — Mechanical checks (MAX 3 CYCLES)
```
.venv/bin/python scripts/imat_mechanical_checks.py --in work/imat/questions.json --report work/imat/mech_report.json
```
Auto-fixes are applied. Route BLOCKING ids (M3/M4/M5/M6-unfixed/M7/M8/M9/M10) to
`creator-imat`, re-run. Stop after 3 cycles; log leftovers.

## Phase 4 — Semantic QC (MAX 3 CYCLES)
```
.venv/bin/python scripts/recompute_answers.py --in work/imat/questions.json --report work/imat/recompute_report.json
```
Launch a `qc-reviewer-imat` subagent (fresh eyes) using
`.claude/skills/imat-question-qc/SKILL.md` across all questions + the recompute
report. Fix MISMATCH/flagged, re-run. Stop after 3 cycles; log leftovers.

## Phase 5 — Re-run mechanical checks (MAX 2 CYCLES)
Re-run Phase 3's command; fix; stop after 2 cycles.

## Phase 6 — Shuffle + charts + S3 + export + validate + archive
Order matters: render charts, upload them to S3 (so the link is baked into every
question of the set), THEN export (CSV uses the S3 URLs; PDF embeds the local PNG
once per set).
```
.venv/bin/python scripts/imat_shuffle_options.py --in work/imat/questions.json
.venv/bin/python scripts/imat_charts.py --in work/imat/questions.json --assets output/imat_assets
.venv/bin/python scripts/imat_upload_assets.py --in work/imat/questions.json --base output --prefix imat
.venv/bin/python scripts/imat_export_csv.py --in work/imat/questions.json --out output/imat_<MBA|BS>_<YYYY-MM-DD>.csv
.venv/bin/python scripts/imat_export_pdf.py --in work/imat/questions.json --out output/imat_<MBA|BS>_<YYYY-MM-DD>.pdf --title "IIT Jodhpur Qualifier - <MBA|BS>" --blueprints imat/blueprints.json
.venv/bin/python scripts/imat_validate_csv.py --csv output/imat_<MBA|BS>_<YYYY-MM-DD>.csv --questions work/imat/questions.json
```
Use today's date in the filenames (pointer: the paper file name includes the date).
If `imat_validate_csv` exits non-zero, STOP and report. Then archive a dated,
never-deleted copy (into `output/imat_real/<date>/`, assets flattened) and record
the shipped questions in the IMAT bank (run `add` exactly ONCE, at the very end,
after all edits — so the bank stores the final wording):
```
cp work/imat/questions.json output/imat_<MBA|BS>_<YYYY-MM-DD>_questions.json
.venv/bin/python scripts/archive_paper.py --dir output/imat_real --move --files output/imat_<MBA|BS>_<YYYY-MM-DD>.csv output/imat_<MBA|BS>_<YYYY-MM-DD>.pdf output/imat_<MBA|BS>_<YYYY-MM-DD>_questions.json --assets-dir output/imat_assets --flatten-assets
.venv/bin/python scripts/question_bank.py add --in work/imat/questions.json --bank bank/imat_history.jsonl
```
(`imat_upload_assets.py` reads AWS creds from `.env`; pass `--dry-run` to compute
URLs without uploading. The cross-run dedup `question_bank.py check` in Phase 2
is now backed by a MinHash+LSH index — sub-second even at 1000+ banked questions,
zero model tokens.)

Ship: the dated `output/imat_real/<date>/` folder (CSV + PDF + chart PNGs) plus
`work/imat/questions.json` (+ `output/imat_unresolved_report.md` if any drops).

**Hard stops:** Phase 2 cross-run dedup = 2 attempts, Phase 3 = 3 cycles,
Phase 4 = 3 cycles, Phase 5 = 2 cycles, single-question regen = 2 attempts then
drop to unresolved. The pipeline must always terminate and export what passed.
