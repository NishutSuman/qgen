# Skill: question-creation

Produce CAT-level, single-correct, 4-option MCQs that are mathematically
correct, unambiguous, bias-free, and free of answer-leaking surface cues.

## The bar (every question must clear all of these)

1. **One defensible answer.** If a careful solver can justify a second option,
   rewrite the stem until only one holds.
2. **Error-mapped distractors.** Each of the 3 wrong options must correspond to
   a real mistake: wrong formula, off-by-one/fencepost, sign error, unit slip,
   averaging instead of weighting, using diameter for radius, etc. State the
   mapping in `explanation` — but refer to each distractor by its VALUE/content,
   never by position ("Option 3"/"(C)"): options are shuffled before export, so
   position labels go stale. `mechanical_checks.py` M4 blocks position references.
   No joke options, no absurd magnitudes.
3. **No surface cues.** The correct option must NOT be the only one with units,
   parentheses, a symbol (× ÷ √ π ° % ₹ $), terminal punctuation, or a distinct
   capitalization/length pattern. Keep all four options the same surface style
   and within ~±12% length of each other; the **correct option must NOT be the
   longest** (students guess "longest = correct" on AI papers) -- `mechanical_checks.py`
   flags this. Vary which index is correct across the paper. **No em-dashes /
   en-dashes** anywhere -- an AI-writing tell; use commas or hyphens.
4. **Self-contained.** All data needed is in the stem. No outside general
   knowledge unless `notes` allows it. Replace region-specific references with
   neutral variables (e.g. "Country A / Policy P") to remove knowledge bias.
5. **LaTeX hygiene** (markdown questions only): balanced `$...$`, use
   `\frac{a}{b}` (never `\frac{a},{b}`), no raw `\uXXXX`. Use `content_type:
   "text"` whenever no math notation/table/chart is needed.
6. **Difficulty honesty.** The realized question must feel like its label.
   - `0` (easy): one concept, one step, ~8–15s expert.
   - `0.5` (medium): 2–3 steps or a small twist, ~18–30s expert.
   - `1` (hard): multi-step, a non-obvious insight, or careful case-work,
     ~25–55s expert.

## Timing logic (attach per question)

- `t_expert_sec`: time for a strong solver who sees the path immediately.
- `t_average_sec`: time for a well-prepared average student.
- Keep `t_average_sec / t_expert_sec` roughly in the question's
  `target_discrimination_band` (guidance only): easy ≈ 4–6, medium ≈ 6–7.5,
  hard ≈ 7.5–9. Anchor to true cognitive load, not the label alone.
- Do **not** write `discrimination_ratio` — a script computes it.

## Verification block (attach whenever the answer is computable)

Add a `verification` object so `recompute_answers.py` can independently confirm
the key. `expr` is a tiny Python snippet (statements separated by `;`) whose
LAST expression evaluates to the correct option string `"1".."4"`. Available:
`math`, `Fraction`, `gcd`, `comb`, `factorial`, `combinations`,
`permutations`, `product`.

Example (profit %):
```json
"verification": {
  "expr": "cp=900/60; sp=18; p=round((sp-cp)/cp*100); '3' if p==20 else '0'",
  "expected": "3"
}
```
For pure verbal/logic questions with no closed form, omit `verification`; the
QC skill will clear them by reasoning instead.

## Topic spread

Draw from: arithmetic/commercial math, number theory, algebra, geometry
(2D/3D), probability & sets, data interpretation, logical reasoning, series &
patterns, data sufficiency, inequalities. Respect inclusions/exclusions in
`notes`.

## Answer position

Always place the correct answer at position `"1"` in your draft (`correct_answer: "1"`).
`scripts/shuffle_options.py` runs after all QC phases and will relocate every
correct answer to a balanced random position before export. Do NOT attempt to
vary or balance positions yourself — the script owns that entirely.

## Self-check before returning

Run the **question-qc** skill on your own chunk and fix what you can. Confirm:
4 non-empty distinct options, valid `correct_answer`, balanced `$`, a
`verification` block where computable, and no obvious surface cue on the key.
