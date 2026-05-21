# Run Report — CAT-Level MCQ Paper

**Generated:** 2026-05-21  
**Command:** `--count 50 --difficulty "0:10, 0.5:20, 1:20" --notes "" --id-start 1`

---

## Plan vs Requested

| Metric | Requested | Delivered |
|--------|-----------|-----------|
| Total questions | 50 | 50 |
| Easy (0) | 10 | 10 |
| Medium (0.5) | 20 | 20 |
| Hard (1) | 20 | 20 |

---

## Phase Cycle Counts

| Phase | Cycles Used | Cap |
|-------|-------------|-----|
| Phase 3 — Mechanical checks | 2 | 3 |
| Phase 4 — Semantic QC       | 2  | 3 |
| Phase 5 — Re-mechanical     | 1 | 2 |

---

## Mechanical Check Summary

- M1: 1 item(s)

---

## Semantic QC Summary

### Recompute verdicts

| Verdict | Count |
|---------|-------|
| MATCH | 49 |
| UNCHECKABLE | 1 |

### QC reviewer

| Action | Count |
|--------|-------|
| PASS (clean) | 47 |
| fix_in_place | 3 |
| route_to_creator | 0 |

---

## Answer-Position Histogram

| Position | Count | % |
|----------|-------|---|
| 1 | 13 | 26.0% |
| 2 | 13 | 26.0% |
| 3 | 12 | 24.0% |
| 4 | 12 | 24.0% |

Longest-correct: **26.0%**

---

## Discrimination Ratio Summary

| Band | Min | Max | Mean | Target |
|------|-----|-----|------|--------|
| Easy (0)      | min=4.2  max=5.0  mean=4.6   | 4–6   |
| Medium (0.5)  | min=5.5  max=7.0  mean=6.2 | 6–7.5 |
| Hard (1)      | min=7.7  max=8.5  mean=8.0   | 7.5–9 |

---

## Output Files

| File | Description |
|------|-------------|
| `output/paper.csv` | Platform CSV, 50 rows |
| `output/paper_answer_key.md` | Answer key with full solutions |
| `work/questions.json` | Full question set with all metadata |
| `work/qc_report.json` | Final QC verdicts |
| `work/recompute_report.json` | Answer verification report |

**Unresolved items:** None.
