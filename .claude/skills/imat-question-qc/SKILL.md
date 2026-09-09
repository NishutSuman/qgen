# Skill: imat-question-qc

Audit IMAT questions for correctness and fairness (semantic judgment). The
deterministic surface checks — option counts, position, cues, encoding, set
contiguity, stimulus-identical-across-set — are handled by
`scripts/imat_mechanical_checks.py`; do not duplicate those. Build on the base
`question-qc` skill and add the IMAT items below.

For each question output `PASS` or
`FLAG{reasons[], suggested_fix, action}` (`fix_in_place` | `route_to_creator`).

## Checks

1. **Correctness.**
   - Numeric/closed-form (all QA/DILR, many logic sets): cross-check
     `work/imat/recompute_report.json`. Any `MISMATCH`/`ERROR` → automatic FLAG.
   - For TITA, confirm the `tita_answer` is the unique numeric truth and matches
     `verification.expected`.
   - Re-derive logic and verbal (VARC) answers by reasoning; confirm uniqueness.

2. **Set coherence (VARC/DILR sets).**
   - The stimulus fully specifies every question in the set; no question needs
     information outside the attached passage/table/graph.
   - Stimulus is self-contained per question (it should already be identical
     across the set — if not, route to creator).
   - For graph sets, the `chart` spec data actually supports the stated answer.

3. **Pattern fidelity.** RC tests the passage; odd-one-out has exactly one misfit
   among 5; para-jumble has one defensible order; summary option is the best (not
   just acceptable) summary. DILR logic sets are uniquely determined.

4. **Ambiguity / distractors / bias** — as in base QC: one defensible answer,
   error-mapped distractors, neutral framing.

5. **Difficulty & timing** match the slot label and the real solve path
   (including stimulus reading time). If you change timings, re-run
   `scripts/compute_ratios.py`.

## Correction rules

- Small, clear fixes → `fix_in_place` in `work/imat/questions.json`. If you edit a
  shared-set stimulus, apply the SAME edit to every member of the set.
- Wrong answer / ambiguous / off-pattern / off-difficulty → `route_to_creator`
  with the ids and reason.
- Never change a key without fixing the explanation and `verification`.

## Output

Write `work/imat/qc_report.json`: a list of
`{id, verdict, reasons[], suggested_fix, action}`. Touch only flagged questions.
Respect the orchestrator's cycle caps; surface anything unresolved so it lands in
`output/imat_unresolved_report.md` rather than looping.
