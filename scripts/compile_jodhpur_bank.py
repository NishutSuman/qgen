#!/usr/bin/env python3
"""compile_jodhpur_bank.py — merge the 5 IIT Jodhpur IMAT papers into ONE
internal-schema list, grouped by variant (MBA, then BS) and, within a variant,
by section (all VARC together, then DILR, then QA). Feeds imat_export_pdf.py.

Sources: 3 papers have internal question JSONs (kept as-is, with worked
solutions); the 2 BS-only papers are reconstructed from their platform CSVs
(sets rebuilt from setId; stimulus = contentBody minus its final question block).
Set ids are prefixed per paper so members never collide after the merge.
"""
import argparse
import csv
import json
from collections import defaultdict

# (variant, paper_tag, kind, path) — order within a variant is chronological.
PAPERS = [
    ("MBA", "MBA1", "json", "output/imat_real/2026-07-23/imat_MBA_2026-07-23_questions.json"),
    ("MBA", "MBA2", "json", "output/imat_real/2026-07-31/imat_MBA_2026-07-31_questions.json"),
    ("BS", "BS1", "csv", "output/imat_real/2026-06-25/imat_BS_2026-06-25.csv"),
    ("BS", "BS2", "csv", "output/imat_real/2026-07-23/imat_BS_2026-07-23.csv"),
    ("BS", "BS3", "json", "output/imat_real/2026-07-31/imat_BS_2026-07-31_questions.json"),
]
VARIANT_RANK = {"MBA": 0, "BS": 1}
SECTION_RANK = {"VARC": 0, "DILR": 1, "QA": 2}


def prefix_set(tag, sid):
    return f"{tag}-{sid}" if sid else ""


def load_json_paper(variant, tag, path):
    out = []
    for q in json.load(open(path, encoding="utf-8")):
        q = dict(q)
        q["variant"] = variant
        q["paper"] = tag
        q["set_id"] = prefix_set(tag, q.get("set_id", ""))
        out.append(q)
    return out


def diff_val(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.5


def load_csv_paper(variant, tag, path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    groups = defaultdict(list)
    order = []
    for r in rows:
        sid = r["setId"]
        key = sid or f"__solo_{len(order)}"
        if key not in groups:
            order.append(key)
        groups[key].append(r)

    out = []
    for key in order:
        members = groups[key]
        sid = members[0]["setId"]
        shared = bool(sid) and len(members) > 1
        section = members[0]["section"]
        kind = "passage" if section == "VARC" else ("data" if section == "DILR" else "none")
        stim = ""
        if shared:
            blocks = members[0]["contentBody"].split("\n\n")
            stim = "\n\n".join(blocks[:-1]).strip()
        for seq, r in enumerate(members, 1):
            qtype = r["questionType"]
            body = r["contentBody"]
            if shared:
                qtext = body.split("\n\n")[-1].strip()
            else:
                qtext = body.strip()
            opts = {str(i): r.get(f"option.{i}", "") for i in range(1, 6)
                    if r.get(f"option.{i}", "")}
            rec = {
                "question_id": 0,
                "variant": variant,
                "paper": tag,
                "section": section,
                "set_id": prefix_set(tag, sid),
                "set_seq": seq if shared else "",
                "set_size": len(members) if shared else 1,
                "shared_set": shared,
                "kind": kind if shared else "none",
                "question_type": qtype,
                "num_options": len(opts),
                "topic": r.get("tagRelationships", ""),
                "difficulty": diff_val(r.get("difficultyLevel")),
                "stimulus": {"kind": kind if shared else "none",
                             "markdown": stim if shared else ""},
                "question_text": qtext,
                "explanation": "",
                "t_average_sec": r.get("prepTime(in_seconds)", ""),
            }
            if qtype == "mcsc":
                rec["options"] = opts
                rec["correct_answer"] = r.get("mcscAnswer", "")
            else:
                rec["tita_answer"] = r.get("intAnswer", "") or r.get("fitbAnswer", "")
            out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="work/aai/jodhpur_bank.json")
    args = ap.parse_args()

    merged = []
    for variant, tag, kind, path in PAPERS:
        recs = (load_json_paper if kind == "json" else load_csv_paper)(variant, tag, path)
        merged += recs
        print(f"  {tag} ({variant}, {kind}): {len(recs)} questions")

    # Group MBA first then BS; within a variant, all VARC, then DILR, then QA.
    # Stable sort keeps paper order and each set's members contiguous.
    merged.sort(key=lambda r: (VARIANT_RANK.get(r["variant"], 9),
                               SECTION_RANK.get(r["section"], 9)))
    for i, r in enumerate(merged, 1):
        r["question_id"] = i
        r["band"] = f"{r['variant']} — {r['section']}"

    json.dump(merged, open(args.out, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

    from collections import Counter
    print(f"[OK] {len(merged)} questions -> {args.out}")
    for v in ("MBA", "BS"):
        c = Counter(r["section"] for r in merged if r["variant"] == v)
        print(f"  {v}: total {sum(c.values())} | " + " ".join(f"{s} {c[s]}" for s in ["VARC", "DILR", "QA"]))


if __name__ == "__main__":
    main()
