# CLAUDE.md — CAT-Level MCQ Generator

This repo generates national-scale, CAT-level **single-correct 4-option MCQs**
(`mcsc`) end-to-end, with deterministic verification and hard stops.

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
2. **Parallel create + self-QC** — `creator` subagents, 20 questions each, own
   file per agent → merge → `compute_ratios.py`
3. **Mechanical checks** — `scripts/mechanical_checks.py` (max 3 cycles)
4. **Semantic QC** — `qc-reviewer` subagent + `recompute_answers.py` (max 3)
5. **Re-run mechanical checks** (max 2)
6. **Export** — `export_csv.py` (platform CSV) + `export_md.py` (answer key)

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
scripts/*.py                             all deterministic logic
work/                                    intermediate JSON (plan, chunks, reports)
output/                                  paper.csv, paper_answer_key.md, run_report.md
```

## Rules of the house

- Verify, don't trust: numeric keys ship only after `recompute_answers.py`.
- Scripts for the mechanical, model for the semantic.
- QC reviewer ≠ the agent that wrote the question.
- Every loop terminates; unresolved items are reported, never looped on.
