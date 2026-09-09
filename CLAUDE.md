# CLAUDE.md — CAT-Level MCQ Generator

This repo generates national-scale, CAT-level **single-correct 4-option MCQs**
(`mcsc`) end-to-end, with deterministic verification and hard stops.

> **Two pipelines — never mix them.** This repo runs two separate flows. Pick by
> the request: if it says **IMAT / MBA / BS** or uses `/generate-imat`, it's the
> IMAT flow; otherwise it's the normal `mcsc` flow. They never share scripts,
> banks, work dirs, or outputs, and the exporters hard-stop if fed the other's
> data (IMAT records carry a `section` field; normal ones don't).
>
> | | Normal (`mcsc`) | IMAT (CAT-pattern) |
> |---|---|---|
> | Command | `/generate-questions` | `/generate-imat --paper MBA\|BS` |
> | Runner | `python` | `.venv/bin/python` (matplotlib + boto3) |
> | Scripts | `scripts/*.py` | `scripts/imat_*.py` |
> | Work dir | `work/` | `work/imat/` |
> | Bank | `bank/history.jsonl` | `bank/imat_history.jsonl` |
> | Outputs | `output/paper.csv`, `paper_answer_key.md` | `output/imat_paper.csv` + `.pdf` + `imat_assets/` |
>
> **IMAT papers** (VARC/DILR/QA, MBA & BS variants, sets + TITA + charts) are
> documented in **`IMAT.md`**. Cross-run dedup for both banks uses the fast
> MinHash+LSH index in `scripts/bank_index.py`. Everything below is the original
> `mcsc` flow.

## Run it

```
/generate-questions --count 50 --difficulty "0:8, 0.5:18, 1:24" --notes "CAT-level quant + LR + DI. No calculus. Strong error-mapped distractors."
```

`--difficulty` per-level counts MUST sum to `--count`. Levels: `0` easy,
`0.5` medium, `1` hard.

## Pipeline (each loop has a hard stop — see the command file)

0. **Validate command** — `scripts/validate_command.py` (stop on mismatch)
1. **Central `plan.json`** — intent only (`type, topic, difficulty`); validated
   against the command by `scripts/validate_plan.py`
2. **Parallel create + self-QC** — `question_bank.py digest` (cross-run
   avoid-list) → `creator` subagents, 20 questions each, own file per agent →
   merge → `compute_ratios.py` → `question_bank.py check` (cross-run dedup gate,
   max 2 regen attempts)
3. **Mechanical checks** — `scripts/mechanical_checks.py` (max 3 cycles)
4. **Semantic QC** — `qc-reviewer` subagent + `recompute_answers.py` (max 3)
5. **Re-run mechanical checks** (max 2)
6. **Shuffle + Export** — `shuffle_options.py` (balance answer positions) → `export_csv.py` + `export_md.py` → `question_bank.py add` (record shipped Qs)

## Where the timing fields live

`plan.json` is intent-only. `t_expert_sec` / `t_average_sec` are attached during
**creation** (Phase 2). `discrimination_ratio` is **derived** (`t_average ÷
t_expert`) and computed by script — never authored. The four behavioral bands
(`t_student < t_expert_floor`, …) are interpretation logic, documented in
`README.md`, not stored on questions.

## Layout

```
.claude/commands/generate-questions.md   slash command (orchestrator)
.claude/agents/creator.md                generation subagent (20 Qs)
.claude/agents/qc-reviewer.md            fresh-eyes QC subagent
.claude/skills/question-creation/SKILL.md creation quality bar
.claude/skills/question-qc/SKILL.md      QC checks
scripts/validate_command.py              Phase 0: command arg validation
scripts/validate_plan.py                 Phase 1: plan vs command (+ topic spread)
scripts/merge_chunks.py                  Phase 2: merge creator chunks
scripts/set_content_type.py              Phase 2: auto-detect content_type (text/markdown)
scripts/compute_ratios.py                Phase 2: discrimination_ratio
scripts/question_bank.py                  Phase 2/6: cross-run dedup (digest/check/add)
scripts/mechanical_checks.py             Phases 3+5: M1-M9 checks + auto-fixes
scripts/recompute_answers.py             Phase 4: numeric answer verification
scripts/shuffle_options.py               Phase 6: shuffle options + balance positions
scripts/export_csv.py                    Phase 6: platform CSV
scripts/export_md.py                     Phase 6: answer key markdown
scripts/validate_csv.py                  Phase 6: CSV header + row count check
scripts/generate_run_report.py           Final: deterministic run_report.md
work/                                    intermediate JSON (plan, chunks, reports)
bank/history.jsonl                        append-only bank of shipped questions (cross-run dedup)
output/                                  paper.csv, paper_answer_key.md, run_report.md
```

## Rules of the house

- Verify, don't trust: numeric keys ship only after `recompute_answers.py`.
- Scripts for the mechanical, model for the semantic.
- QC reviewer ≠ the agent that wrote the question.
- Every loop terminates; unresolved items are reported, never looped on.

## What the LLM must NOT do (scripts own these)

| Field / task | Script that owns it |
|---|---|
| `content_type` (text vs markdown) | `set_content_type.py` |
| `discrimination_ratio` | `compute_ratios.py` |
| Answer-position balancing / shuffling | `shuffle_options.py` |
| `run_report.md` | `generate_run_report.py` |
| CSV validation | `validate_csv.py` |
| Cross-run de-duplication (vs past papers) | `question_bank.py` |
