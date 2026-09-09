# Skill: imat-question-creation

Produce CAT-pattern IMAT questions across three sections — VARC, DILR, QA —
matching the exact patterns of the reference papers, with the quality bar of the
base `question-creation` skill PLUS the IMAT-specific rules below.

## Record shape (append to your chunk file `work/imat/questions_chunk_<N>.json`)

```json
{
  "question_id": 12,
  "section": "DILR",
  "set_id": "DILR-3",
  "set_seq": 2,
  "set_size": 4,
  "shared_set": true,
  "kind": "table",
  "question_type": "mcsc",
  "num_options": 4,
  "topic": "DILR/di-table",
  "difficulty": 1,
  "stimulus": {
    "kind": "table",
    "markdown": "Units Sold\n| Product | A | B |\n|---|--:|--:|\n| X | 10 | 20 |"
  },
  "question_text": "Only the final question prompt goes here.",
  "options": { "1": "...", "2": "...", "3": "...", "4": "..." },
  "correct_answer": "1",
  "explanation": "Worked solution + error-mapped distractors.",
  "t_expert_sec": 35, "t_average_sec": 240,
  "verification": { "expr": "...; '1' if ... else '0'", "expected": "1" }
}
```

Carry `question_id, section, set_id, set_seq, set_size, shared_set, kind,
question_type, num_options, topic, difficulty` through EXACTLY as given in the
plan slot. Always draft the correct answer at position `"1"`
(`imat_shuffle_options.py` relocates it). Do NOT set `content_type` or
`discrimination_ratio` — scripts own those.

## Stimulus rules (the critical IMAT constraint)

- A **shared set** (`shared_set: true`, kind `passage`/`table`/`graph`) shares ONE
  stimulus. Put the **full stimulus in every member's `stimulus` field, byte-for-byte
  identical** — each question is uploaded separately and must stand alone, so the
  student never has to scroll back.
- `question_text` holds ONLY the changing prompt; the passage/table/graph lives in
  `stimulus.markdown` (and `stimulus.chart` for graphs), never duplicated into the prompt.
- **State units in the stimulus TEXT, never only on a chart axis/title.** If a chart
  plots units in thousands or prices in rupees, say so in `stimulus.markdown`
  (e.g. "Units shipped are in thousands and prices are in rupees per unit; revenue =
  units x price"). A reader must be able to compute the answer from the words alone —
  an axis label like "(in '000)" is not sufficient and causes 1000x scale mistakes.
- **Tables → markdown** in `stimulus.markdown`. **Graphs →** a `stimulus.chart` spec
  (a single object or a list); `imat_charts.py` renders the PNG. Example chart spec:
  ```json
  "chart": [{ "type": "grouped_bar", "title": "Units Sold (in '000)",
              "y_label": "Units ('000)", "categories": ["ProBook","ZenBook"],
              "series": { "Q1": [4,3], "Q2": [5,2.5], "Q3": [6,4.5] } }]
  ```
  For graph sets you may also put a one-line intro in `stimulus.markdown`.
- Singletons (`shared_set: false`, kind `none`) have no stimulus — the whole question
  (e.g. the 5 sentences of an odd-one-out) lives in `question_text`.

## Section patterns (do not compromise)

- **VARC**: RC (4–5 Q per passage, passage in stimulus) · odd-one-out (5 options A–E,
  5 sentences in the prompt, one is the misfit) · para-jumble (4 options, sentences
  1–4 to be ordered, options are sequences like "3142") · summary (4 options, best
  summary of a paragraph given in the prompt).
- **DILR**: each set = a stimulus (logic scenario text / markdown table / chart) + its
  questions. Logic sets need a uniquely determined solution.
- **QA**: standalone. `mcsc` (4 options) and `tita` (numeric type-in: NO options, put
  the answer in `tita_answer`, omit `options`/`correct_answer`).

## Candidate instructions are OWNED BY THE BLUEPRINT (do not hand-write them)

For RC/summary/DI-table/DI-graph/logic groups the blueprint carries an
`instruction` line (e.g. "Read the following passage carefully and answer the
question that follows."). `imat_export_csv.py` prepends it to EVERY question of
that set automatically, because each question is uploaded standalone. So:
- Do NOT put a set-level directive into `stimulus.markdown` or `question_text`
  for those groups — it would appear twice. Start the stimulus with the passage /
  caption+table / scenario itself.
- Odd-one-out and para-jumble DO keep their own in-body instruction line (their
  task description is part of the item), and they have no blueprint instruction.
- QA and GA standalone questions get no instruction at all.

## Question-text formatting (markdown — keep instruction, body, question apart)

`question_text` is rendered as markdown in both the CSV and the PDF, so structure it:
- **RC and DILR set questions:** the body (passage / table / chart) lives in `stimulus`;
  `question_text` is ONLY the question, wrapped in bold: `**How many points did England score?**`.
  (Export adds a blank line between the stimulus and the question automatically.)
- **Odd-one-out / para-jumble (singletons):** put the instruction, then a blank line,
  then each numbered sentence on its OWN line, then a blank line, then the bold question:
  `<instruction>\n\n(1) ...\n(2) ...\n(3) ...\n\n**Which sentence is the odd one out?**`
- **Summary (singleton):** the paragraph, a blank line, then the bold question:
  `<paragraph>\n\n**Which of the following best summarises the paragraph?**`
- **QA:** a single plain prompt (no body) — no bold needed.

Use `\n\n` for paragraph breaks and `\n` for line breaks; wrap the actual question in
`**...**` so it stands out. Never run the instruction and the question into one line.

## No AI tells (hard requirements — scripts also enforce these)

- **Option length parity.** Keep all options within ~±12% length of each other. The
  correct option must **NOT be the longest** — students game AI papers by picking the
  longest choice. `imat_mechanical_checks.py` (M11) flags and blocks any question where
  the key is noticeably the longest; you will be routed to fix it, so balance lengths
  up front (expand the shorter distractors with plausible wrong detail, or trim the key).
- **No em-dashes or en-dashes** ("—" / "–") anywhere — a classic AI-writing tell. Use
  commas, hyphens, or rewordings. (The script strips any that slip through, but write
  clean.)
- **Explanations must not cite option positions** ("Option 3", "(C)", "choice B").
  Options are shuffled before export, so position labels go stale. Refer to the
  option's VALUE/content instead (e.g. "the 20% figure is right because…; the 25%
  trap comes from using SP as the base"). `imat_mechanical_checks.py` M4 blocks this.

## Difficulty & timing

Honor the plan slot's `difficulty` (0/0.5/1) — MBA skews hard, BS lighter; the
realized item must feel like its label. Attach realistic `t_expert_sec` /
`t_average_sec` (ratio ~4–9). Reading time for set questions counts the stimulus.

## Verification

Attach a `verification` block wherever the answer is computable (all QA/DILR
numeric, many logic sets). The last expression must evaluate to the option string
("1".."N") for mcsc, or to the exact `tita_answer` string for TITA. Pure verbal
(VARC) items omit it — QC clears them by reasoning. For TITA set
`verification.expected` = the tita answer string.

**Keep the expr shuffle-safe.** Draft the correct answer at position "1" and make
the success value a plain literal in the LAST segment: `...; '1' if <condition on
the VALUES> else '0'`. The shuffle repoints that `'1'` to the option's new
position. Do NOT encode option positions inside the expr (e.g.
`opts={'1':1.6,'2':1.5,...}; min(opts, key=...)`) — that mapping cannot be
repointed and goes stale after shuffling. Test the correct VALUE directly, e.g.
`r=968/608; '1' if abs(r-8/5) < abs(r-3/2) and abs(r-8/5) < abs(r-5/3) and
abs(r-8/5) < abs(r-7/4) else '0'`.

## Self-check before returning

Run the **imat-question-qc** skill on your chunk. Confirm: stimulus identical
across each set and attached to every member; correct option count per item
(4, or 5 for odd-one-out; none for TITA); valid key; balanced `$`; verification
present where computable; no surface cue on the key.
