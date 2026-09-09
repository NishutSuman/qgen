# IMAT paper generator (CAT-pattern)

Separate, self-contained pipeline for the **IMAT** test — three sections (VARC,
DILR, QA), two fixed variants (**MBA** harder, **BS** lighter). It mirrors the
`generate-questions` pipeline step-for-step but with `imat_*` scripts, a separate
command, and a separate question bank. Nothing here touches the normal `mcsc`
flow.

## Run it

```
.venv/bin/python -V                       # the IMAT pipeline uses the project venv
/generate-imat --paper MBA                # base count
/generate-imat --paper BS --count 64      # ±5% of base only
```

`--paper` (MBA | BS) fixes BOTH structure and difficulty — there is no
`--difficulty` knob. `--count` is optional and may differ from the variant base
by at most ±5%; the delta is absorbed entirely by the QA MCQ pool. `--tita N`
optionally sets the TITA count anywhere in `tita_range` (4–8); the MCQ pool
compensates so the section/total hold. Patterns and difficulty never change.
Either variant may include DI **table or graph** sets (BS's DILR-5 is a graph).

## No AI "tells" (enforced)

- **Length parity:** the correct option must not be the longest. `imat_mechanical_checks.py`
  M11 blocks any item where the key is noticeably the longest, and caps the
  batch rate — students must not be able to guess "longest = correct."
- **No em/en dashes** ("—"/"–"): auto-stripped everywhere (M6) as an AI-writing tell.
- The creation skills state both rules up front so creators avoid them.

## Why a venv

Charts and the verification PDF use **matplotlib** (not stdlib). Install once:

```
python3 -m venv .venv && .venv/bin/pip install matplotlib
```

Every IMAT command runs through `.venv/bin/python`. The plan/validate/merge/
mechanical/bank scripts are pure stdlib, but running them all through the venv
keeps the pipeline consistent.

## Structure (blueprints)

`imat/blueprints.json` is the source of truth: per variant, an ordered list of
groups with `section, kind, qtype, num_options, size, topic, difficulty`. A group
with `kind != "none"` is a **shared set** (one stimulus, one platform config);
`kind "none"` groups are singletons. `flex: true` marks the pool the ±5% delta
moves. Edit this file to change the paper shape.

Reference shapes captured from the sample papers:
- **MBA** (base 68): VARC 24 (RC 5+4, odd-one-out 4, para-jumble 5, summary 6),
  DILR 22 across 6 sets (logic ×4, table, graph), QA 22 (17 mcsc + 5 tita).
- **BS** (base 66): VARC 24 (RC 4+4+4, odd-one-out 3, para-jumble 4, summary 5),
  DILR 18 across 5 sets (logic ×3, table ×2), QA 24 (18 mcsc + 6 tita).

## Set mode + stimulus attachment (platform constraint)

VARC and DILR are **set mode**: each set must become ONE config holding only that
set's questions, in consecutive configs. So:
- Questions are generated and kept **grouped by set**; the CSV carries
  `section, setId, setSeq` so you can build the configs directly.
- The **stimulus (passage / markdown table / chart) is attached to every question
  in the set, identical across the set** — each question is uploaded separately
  and must stand alone (the student never scrolls back). `imat_merge_chunks.py`
  and `imat_mechanical_checks.py` (M10) enforce this.
- For OR-choices / per-student variation in set sections, the unit of
  substitution is the **whole set**, never an individual question.

## Tables vs graphs, and S3

- **Tables → markdown** in `stimulus.markdown`.
- **Graphs → a `stimulus.chart` spec**; `imat_charts.py` renders a grouped-bar
  **PNG** into `output/imat_assets/`. `imat_upload_assets.py` then uploads each PNG
  to the org S3 bucket and writes the public URL into `stimulus.image_urls` on
  **every question of the set** — so a chart shared by 5 questions gets one upload
  and the same link baked into all 5 (no manual link pasting per question).
  - Credentials come from a **gitignored `.env`** (`AWS_*`). Rotate the key that
    was shared in chat; prefer an IAM user scoped to `s3:PutObject` on the bucket.
  - `--dry-run` computes the URLs without uploading (offline / tests).
  - S3 key = `imat/<date>/<file>.png`.
- The **CSV** embeds the S3 URL in each question's body (every set question is
  self-contained). The **PDF** embeds the local PNG **once per set** (it is for
  human verification, so the chart need not repeat 5×).

## Cross-run de-duplication (fast)

`question_bank.py check --bank bank/imat_history.jsonl` is backed by
`bank_index.py` — exact repeats via a fingerprint set, near-duplicates via
**MinHash + LSH** (candidate retrieval, not an all-pairs scan), with bank
signatures cached to a sidecar. Checking against a 1000+ bank is sub-second and
costs **zero model tokens** (it is a script, not the model reading the bank).

## Deliverables, PDF and archiving

- **CSV** (`output/imat_paper.csv`) — upload file; stimulus (markdown table or S3
  chart URL) embedded in every question's body.
- **PDF** (`output/imat_paper.pdf`) — reportlab verification paper: cover with
  exam metadata (2-hour duration, 40-min sections, max marks, marking scheme,
  instructions), navy section bars, each set's stimulus shown ONCE (chart embedded
  once), questions with options, the correct answer in green, and solutions.
- **Archive:** after the CSV validates, `archive_paper.py` snapshots the CSV + PDF
  (+ flattened chart PNGs) into **`output/imat_real/<date>/`** (suffixed `_2`… if it
  exists). The normal `mcsc` flow archives to **`output/mcsc_real/<date>/`** — kept
  separate, with separate banks (`bank/history.jsonl` vs `bank/imat_history.jsonl`).
  Papers are never deleted.

The shuffle (`imat_shuffle_options.py`) repoints each `verification.expr`'s success
literal to the new position, so `recompute_answers.py` stays valid (all MATCH) even
after shuffling — the archived `questions.json` is self-verifiable.

## Deliverables & PDF↔CSV parity

Phase 6 produces, all from the same `work/imat/questions.json`:
- `output/imat_paper.csv` — upload file (self-contained `contentBody` per row).
- `output/imat_paper.pdf` — institute **verification** paper (stimulus, options,
  marked answer ✓, solution).
- `output/imat_assets/*.png` — chart images.

`imat_validate_csv.py` proves the CSV faithfully reflects the source (header,
row-per-question, `contentBody` and answer parity). The PDF is generated from the
same source via the shared `imat_render.py`, so verifying the PDF == verifying the
upload.

## Scripts

| Script | Phase | Job |
|---|---|---|
| `imat_validate_command.py` | 0 | `--paper`, `--count` ±5% gate |
| `imat_plan.py` / `imat_validate_plan.py` | 1 | expand blueprint → plan; validate sets/counts |
| `imat_merge_chunks.py` | 2 | merge creator chunks; enforce set + stimulus invariants |
| `imat_mechanical_checks.py` | 3,5 | M1–M10 (set/TITA/5-option aware) |
| `imat_shuffle_options.py` | 6 | shuffle mcsc options, balance per option-count, keep set order |
| `imat_charts.py` | 6 | render grouped-bar PNGs (matplotlib) |
| `imat_export_csv.py` / `imat_export_pdf.py` | 6 | CSV + verification PDF (shared `imat_render.py`) |
| `imat_validate_csv.py` | 6 | CSV ↔ source parity (HARD STOP) |
| reused: `recompute_answers.py`, `compute_ratios.py`, `set_content_type.py`, `question_bank.py --bank bank/imat_history.jsonl` | | numeric verify, ratios, content type, cross-run dedup |

Smoke-test the whole chain without the model:

```
.venv/bin/python scripts/imat_selftest.py
```
