#!/usr/bin/env python3
"""question_bank.py — cross-run de-duplication via a persistent question bank.

This is the *mechanical* half of "don't ship the same question twice". The LLM
must NOT eyeball duplicates across runs — this script owns it. Three verbs:

  digest  Read the bank and write work/bank_recent.json — a bounded list of
          already-used stems for the creator agents to AVOID at generation time.
          Run in Phase 2 BEFORE spawning creators.

  check   Compare every question in work/questions.json against the bank and
          flag any near-duplicate (token Jaccard >= threshold) or exact repeat
          (identical fingerprint). Writes work/bank_report.json. Run after merge
          (Phase 2), before mechanical checks; route flagged IDs to a creator.

  add     Append the shipped, validated questions to bank/history.jsonl
          (append-only JSONL, one record per question). Idempotent: a stem whose
          fingerprint already exists in the bank is skipped. Run in Phase 6
          AFTER export + validate_csv, so only shipped papers enter the bank.

Normalisation mirrors mechanical_checks.py's M5 exactly (tokens = lowercase
[a-z0-9]+, Jaccard over token sets) so cross-run behaviour matches in-run dedup.

Usage:
    python scripts/question_bank.py digest --bank bank/history.jsonl \
        --out work/bank_recent.json [--limit 500]
    python scripts/question_bank.py check  --in work/questions.json \
        --bank bank/history.jsonl --report work/bank_report.json [--threshold 0.8]
    python scripts/question_bank.py add    --in work/questions.json \
        --bank bank/history.jsonl [--paper-id 2026-06-25]

All verbs exit 0 on success (the orchestrator reads the report to decide what to
regenerate). A missing bank file is treated as an empty bank.
"""
import argparse
import datetime
import json
import os

# Shared text/dedup helpers + the fast LSH index live in bank_index.py so the
# same normalisation is used everywhere (and the O(N) scan is gone).
from bank_index import (BankIndex, dedup_text, fingerprint,  # noqa: F401
                        tokens)

JACCARD_DUP = 0.8          # same threshold as mechanical_checks.py M5
DIGEST_LIMIT = 500         # cap stems handed to creators, newest first


def sigcache_path(bank_path):
    return bank_path + ".sigcache.json"


def load_bank(path: str) -> list:
    """Return a list of bank records (dicts). Missing file -> empty bank."""
    if not path or not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def load_questions(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
def cmd_digest(args) -> None:
    bank = load_bank(args.bank)
    # newest entries first; cap so the creator prompt stays bounded
    recent = bank[-args.limit:][::-1]
    out = {
        "count": len(recent),
        "bank_total": len(bank),
        "avoid_stems": [r.get("question_text", "") for r in recent],
        "entries": [
            {
                "question_text": r.get("question_text", ""),
                "topic": r.get("topic", ""),
                "difficulty": r.get("difficulty"),
                "paper_id": r.get("paper_id", ""),
            }
            for r in recent
        ],
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"[OK] digest of {len(recent)} recent stem(s) "
          f"(bank holds {len(bank)}) -> {args.out}")


def cmd_check(args) -> None:
    bank = load_bank(args.bank)
    qs = load_questions(args.inp)

    # Build the exact+LSH index once (bank signatures cached to a sidecar).
    index = BankIndex(bank, cache_path=sigcache_path(args.bank))

    results = []
    flagged = []
    for q in qs:
        qid = q.get("question_id")
        verdict, score, match = index.query(dedup_text(q), args.threshold)
        entry = {"id": qid, "verdict": verdict, "jaccard": score}
        if match is not None:
            entry["matched"] = {"paper_id": match.get("paper_id", ""),
                                "question_id": match.get("question_id")}
            flagged.append(qid)
        results.append(entry)

    report = {
        "threshold": args.threshold,
        "bank_total": len(bank),
        "checked": len(qs),
        "flagged_ids": flagged,
        "results": results,
    }
    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[OK] bank check -> {args.report}")
    print(f"   bank holds {len(bank)} past question(s); checked {len(qs)}")
    if flagged:
        print(f"   [!] {len(flagged)} duplicate(s) of past papers — "
              f"route for regen: {flagged}")
        for r in results:
            if r["verdict"] != "UNIQUE":
                print(f"       Q{r['id']}: {r['verdict']} (jaccard {r['jaccard']}) "
                      f"vs {r['matched']}")
    else:
        print("   no cross-run duplicates")


def cmd_add(args) -> None:
    qs = load_questions(args.inp)
    paper_id = args.paper_id or datetime.date.today().isoformat()

    bank = load_bank(args.bank)
    seen = set()
    for r in bank:
        seen.add(r.get("fingerprint") or fingerprint(r.get("dedup_text")
                                                     or r.get("question_text", "")))

    os.makedirs(os.path.dirname(args.bank) or ".", exist_ok=True)
    added = skipped = 0
    with open(args.bank, "a", encoding="utf-8") as f:
        for q in qs:
            text = q.get("question_text", "")
            ded = dedup_text(q)      # stimulus + prompt, so set questions don't collide
            fp = fingerprint(ded)
            if fp in seen:           # idempotent: never store the same question twice
                skipped += 1
                continue
            seen.add(fp)
            record = {
                "paper_id": paper_id,
                "added": paper_id,
                "question_id": q.get("question_id"),
                "topic": q.get("topic", ""),
                "difficulty": q.get("difficulty"),
                "question_text": text,
                "dedup_text": ded,
                "fingerprint": fp,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            added += 1

    print(f"[OK] bank updated -> {args.bank}")
    print(f"   paper_id={paper_id}  added={added}  skipped(existing)={skipped}  "
          f"bank_total={len(bank) + added}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("digest", help="write recent stems for creators to avoid")
    d.add_argument("--bank", default="bank/history.jsonl")
    d.add_argument("--out", default="work/bank_recent.json")
    d.add_argument("--limit", type=int, default=DIGEST_LIMIT)
    d.set_defaults(func=cmd_digest)

    c = sub.add_parser("check", help="flag questions duplicating the bank")
    c.add_argument("--in", dest="inp", default="work/questions.json")
    c.add_argument("--bank", default="bank/history.jsonl")
    c.add_argument("--report", default="work/bank_report.json")
    c.add_argument("--threshold", type=float, default=JACCARD_DUP)
    c.set_defaults(func=cmd_check)

    a = sub.add_parser("add", help="append shipped questions to the bank")
    a.add_argument("--in", dest="inp", default="work/questions.json")
    a.add_argument("--bank", default="bank/history.jsonl")
    a.add_argument("--paper-id", default=None,
                   help="label for this paper (default: today's date)")
    a.set_defaults(func=cmd_add)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
