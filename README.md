# CAT-Level MCQ Generator

Unzip, open in Claude Code, and run the slash command. The orchestrator drives
everything; you only supply the command.

## Quick start

```
cd qgen
claude            # or open the folder in your Claude Code client
/generate-questions --count 50 --difficulty "0:8, 0.5:18, 1:24" --notes "CAT-level quant + LR + DI. No calculus."
```

Outputs land in `output/`:
- `paper.csv` — platform import format (exact header below)
- `paper_answer_key.md` — exam-style key with the correct option marked
- `run_report.md` — what happened, cycle counts, balance stats
- `unresolved_report.md` — only if something couldn't be resolved within caps

## Requirements

Python 3.9+ (standard library only — no pip installs). The scripts are pure
`json`, `csv`, `math`, `fractions`, `itertools`, `random`, `re`.

Smoke-test the scripts without the model:
```
python scripts/selftest.py
```

## CSV format (verbatim header)

```
questionType,contentType,contentBody,intAnswer,prepTime(in_seconds),floatAnswer.max,floatAnswer.min,fitbAnswer,mcscAnswer,subjectiveAnswer,option.1,option.2,option.3,option.4,mcmcAnswer,tagRelationships,difficultyLevel
```

`mcscAnswer` = correct option digit (1–4). `prepTime(in_seconds)` is mapped from
`t_average_sec`. `difficultyLevel` ∈ {0, 0.5, 1}. Unused columns stay blank.
Extra/unknown columns supplied via `--extra-cols` are appended at the END and
left blank (never removed).

## Timing model

Stored per question: `t_expert_sec`, `t_average_sec`. Derived by script:
`discrimination_ratio = t_average_sec / t_expert_sec`.

The four bands below are how you interpret a *student's* recorded time
`t_student` at scoring time. They are interpretation logic, not fields on a
question:

| Condition | Meaning |
|---|---|
| `t_student < t_expert_floor` | Likely guessed / already knew it (bypassed reasoning) |
| `t_expert_floor ≤ t_student ≤ t_expert_ceiling` | Expert-level student |
| `t_expert_ceiling < t_student ≤ t_average_ceiling` | Normal well-prepared student |
| `t_student > t_average_ceiling` | Struggling or over-thinking |

`Discrimination Ratio = t_average_sec ÷ t_expert_sec` — how much longer an
average student takes than a highly capable one on the same question.

## Cross-run de-duplication (question bank)

Every shipped question is recorded in `bank/history.jsonl` (append-only JSONL,
one record per question with a normalized-token fingerprint). On the next run the
pipeline uses it twice, both owned by `scripts/question_bank.py`:

- **Before generation** — `question_bank.py digest` writes `work/bank_recent.json`,
  an avoid-list of past stems that every `creator` agent reads so it doesn't
  rewrite an old question.
- **After merge** — `question_bank.py check` flags any new question whose stem is
  an exact repeat (identical fingerprint) or a near-duplicate (token Jaccard ≥
  0.8, same threshold as in-run check M5) of a past paper; those IDs are routed
  back to a creator for regen (max 2 attempts).
- **After export** — `question_bank.py add` appends the shipped, validated
  questions to the bank. It is idempotent: a stem already in the bank is skipped.

The bank persists across runs, so re-running the same command produces a
*different* paper rather than repeating questions. Delete `bank/history.jsonl`
to start the history fresh.

## Hard stops (no infinite loops)

| Loop | Cap |
|---|---|
| Cross-run dedup regen (Phase 2) | 2 attempts |
| Mechanical checks (Phase 3) | 3 cycles |
| Semantic QC (Phase 4) | 3 cycles |
| Mechanical re-check (Phase 5) | 2 cycles |
| Single-question regeneration | 2 attempts → unresolved |

The pipeline always terminates and exports whatever passed, with a transparent
report of anything it could not resolve.

## Editing scope

- Change quality rules → edit the two `skills/*/SKILL.md`.
- Change checks/thresholds → edit `scripts/mechanical_checks.py` (constants at
  top: `LONGEST_TOLERANCE`, `POS_MIN/MAX`, `JACCARD_DUP`, ratio bounds).
- Change CSV mapping → edit `scripts/export_csv.py`.
