# Skill: question-qc

Audit each question for correctness and fairness. This is semantic judgment —
the deterministic surface checks (length, position, cues, encoding) are handled
by `scripts/mechanical_checks.py`; do not duplicate those here.

For each question output a verdict: `PASS` or
`FLAG{reasons[], suggested_fix, action}` where `action` is `fix_in_place` or
`route_to_creator`.

## Checks

1. **Correctness.**
   - If the question has numeric/closed-form content, cross-check
     `work/recompute_report.json`. Any `MISMATCH` or `ERROR` → automatic FLAG.
   - Re-derive logic/verbal answers by reasoning. Confirm the stated
     `correct_answer` is the unique truth.

2. **Ambiguity.**
   - Is there exactly one defensible answer? Could a second option be argued?
   - Is the wording precise — units, ranges, "at least"/"exactly"/"not more
     than", inclusive vs exclusive bounds, what "between" means?
   - Are referenced figures/tables fully specified in the stem?

3. **Distractor quality.**
   - All three wrong options plausible and each mapped to a real student error?
   - No duplicate-meaning options; no give-away absurd values.

4. **Bias.**
   - Cultural, regional, gender, language, or knowledge bias that helps some
     test-takers for non-ability reasons? Prefer neutral, abstract framings.

5. **Difficulty & timing match.**
   - Does the realized question match its `difficulty` label?
   - Are `t_expert_sec`/`t_average_sec` realistic for the actual solve path? If
     you change timings, re-run `scripts/compute_ratios.py`.

## Correction rules

- Small, clear fixes (tighten wording, swap a weak distractor, fix a unit):
  `fix_in_place` by editing `work/questions.json`.
- Wrong answer / fundamentally ambiguous / off-difficulty: `route_to_creator`
  with the specific IDs and the reason, so a creator subagent regenerates them.
- Never silently change `correct_answer` without also fixing the explanation
  and (if needed) the `verification` block.

## Output

Write `work/qc_report.json`: a list of
`{id, verdict, reasons[], suggested_fix, action}`. Touch only flagged
questions. Respect the orchestrator's cycle cap — surface anything you cannot
resolve so it lands in `output/unresolved_report.md` rather than looping.
