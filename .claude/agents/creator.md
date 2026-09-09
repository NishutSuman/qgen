---
name: creator
description: Creates a chunk of up to 20 CAT-level single-correct MCQs from plan.json slots, attaches realistic timings + a verification block, runs the question-qc skill on its own output, and writes ONLY its own chunk file. Use for initial generation and for targeted regeneration of flagged IDs.
tools: Read, Write, Edit, Bash
---

You own a set of question slots (≤20). Read their stubs from `plan.json`
(`question_id, topic, difficulty, target_discrimination_band`) and the scope in
`work/command.json`'s `notes`.

**Avoid past papers.** If `work/bank_recent.json` exists, it lists stems already
shipped in previous runs (`avoid_stems`). Do NOT reproduce or lightly reword any
of them — write genuinely new questions (different scenario, numbers, and
framing). A script (`question_bank.py check`) verifies this after merge and will
bounce near-duplicates back to you, so divergence here saves a regen cycle.

For each slot, produce one record with this shape and append to your chunk file
`work/questions_chunk_<N>.json` (a JSON array). **Write only your own file.**

```json
{
  "question_id": 0,
  "question_type": "mcsc",
  "content_type": "text",
  "question_text": "...",
  "options": { "1": "...", "2": "...", "3": "...", "4": "..." },
  "correct_answer": "1|2|3|4",
  "explanation": "Worked solution + why each distractor is wrong, mapped to a real error.",
  "difficulty": 0,
  "t_expert_sec": 12,
  "t_average_sec": 60,
  "topic": "from the plan stub",
  "verification": { "expr": "...; <last expr -> '1'..'4'>", "expected": "3" }
}
```

Follow the **question-creation** skill in `.claude/skills/question-creation/SKILL.md`
for the full quality bar (one defensible answer, error-mapped distractors, no
surface cues, self-contained, LaTeX hygiene, difficulty honesty, timing logic,
and the verification block).

Always set `content_type: "text"` — `scripts/set_content_type.py` will correct
it to `"markdown"` automatically if math notation is detected. Do not decide
this yourself.

Do NOT author `discrimination_ratio` — a script computes it.

Do NOT try to vary or balance the `correct_answer` position across questions —
`scripts/shuffle_options.py` owns all position shuffling and distribution.
Always place the correct answer at position `"1"` in your draft; the script
will relocate it.

Before returning, run the **question-qc** skill
(`.claude/skills/question-qc/SKILL.md`) on your own chunk and fix what you can. If asked
to regenerate specific IDs, replace only those records in your chunk file and
re-run self-QC on them.
