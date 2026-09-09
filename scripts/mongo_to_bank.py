#!/usr/bin/env python3
"""mongo_to_bank.py — turn extractQuestion.py output into the internal IMAT
question schema so imat_export_csv.py / imat_export_pdf.py can build the bank.

    ./.venv/bin/python scripts/mongo_to_bank.py \
        --in work/aai/mongo_questions.json --out work/imat/questions.json
"""
import argparse
import json
import re

SECTION_MAP = {
    "Verbal Ability": "VARC",
    "Data Interpretation & Logical Reasoning": "DILR",
    "Quantitative Ability": "QA",
}
PREP = {"VARC": 100, "DILR": 120, "QA": 90}

# answer keys missing in the source DB, resolved by hand (see run notes).
MANUAL_KEYS = {
    "6969dcd904a6d30e22be4f45": 2,   # car-distance TITA-style mcsc, D = 600
}

H2 = re.compile(r"^##\s+(?!Comprehension\b)(.+)", re.M)


def split_stimulus(body):
    """RC/DI questions carry the passage/scenario, then the actual question as
    the LAST `## ` heading (the leading `## Comprehension` is scaffolding).
    Return (stimulus, question_markdown). No trailing heading -> whole body is
    the question (QA singletons, para-jumbles, odd-one-out)."""
    if not body:
        return "", ""
    body = body.rstrip()
    matches = list(H2.finditer(body))
    if not matches:
        return "", body.strip()
    last = matches[-1]
    stim = body[:last.start()].strip()
    if len(stim) < 150:          # not a real passage -> keep whole body
        return "", body.strip()
    question = "**" + " ".join(last.group(1).split()) + "**"
    return stim, question


def norm_key(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def diff_value(d):
    if d in (0, "0"):
        return 0
    if d in (2, "2"):
        return 1
    return 0.5  # None / 1 -> medium default


def build(data):
    out = []
    qid_counter = 0
    set_counter = {}          # section -> running set number (unique across slots)
    for tmpl in data:
        slot = tmpl["template_name"]
        for block in tmpl["sections"]:
            section = SECTION_MAP.get(block["section_name"], block["section_name"])
            # group by identical, substantial stimulus -> shared sets (RC / DI)
            parsed = [(q, *split_stimulus(q["body"])) for q in block["questions"]]
            groups = {}
            order = []
            for q, stim, ques in parsed:
                key = norm_key(stim) if stim else f"__solo_{q['question_id']}"
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append((q, stim, ques))

            for key in order:
                members = groups[key]
                shared = not key.startswith("__solo_") and len(members) > 1
                set_id = ""
                if shared:
                    set_counter[section] = set_counter.get(section, 0) + 1
                    set_id = f"{section}-SET{set_counter[section]}"
                for seq, (q, stim, ques) in enumerate(members, 1):
                    qid_counter += 1
                    rec = {
                        "question_id": qid_counter,
                        "source_id": q["question_id"],
                        "slot": slot,
                        "section": section,
                        "set_id": set_id,
                        "set_seq": seq if shared else "",
                        "set_size": len(members) if shared else 1,
                        "shared_set": shared,
                        "kind": "passage" if shared else "none",
                        "num_options": len(q["options"]),
                        "topic": f"{section}/{block['section_name']}",
                        "difficulty": diff_value(q["difficulty"]),
                        "t_expert_sec": max(15, PREP[section] // 4),
                        "t_average_sec": PREP[section],
                    }
                    if shared:
                        rec["stimulus"] = {"kind": "passage", "markdown": stim}
                        rec["question_text"] = ques
                    else:
                        rec["stimulus"] = {"kind": "none", "markdown": ""}
                        rec["question_text"] = q["body"].strip()

                    if q["type"] == "int":
                        rec["question_type"] = "tita"
                        rec["tita_answer"] = str(q["int_answer"])
                    else:
                        rec["question_type"] = "mcsc"
                        opts = {str(o["n"]): (o["body"] or "") for o in q["options"]}
                        rec["options"] = opts
                        pos = q["correct_positions"]
                        if pos:
                            rec["correct_answer"] = str(pos[0])
                        elif q["question_id"] in MANUAL_KEYS:
                            rec["correct_answer"] = str(MANUAL_KEYS[q["question_id"]])
                        else:
                            rec["correct_answer"] = ""
                    out.append(rec)
    # Merge across slots into 3 sections: all VARC together, then DILR, then QA.
    # Stable sort keeps slot order and each set's members contiguous within a section.
    rank = {"VARC": 0, "DILR": 1, "QA": 2}
    out.sort(key=lambda r: rank.get(r["section"], 9))
    for i, r in enumerate(out, 1):
        r["question_id"] = i
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/aai/mongo_questions.json")
    ap.add_argument("--out", default="work/imat/questions.json")
    args = ap.parse_args()
    data = json.load(open(args.inp, encoding="utf-8"))
    recs = build(data)
    json.dump(recs, open(args.out, "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    from collections import Counter
    print(f"[OK] {len(recs)} records -> {args.out}")
    print("  sections:", dict(Counter(r["section"] for r in recs)))
    print("  types:", dict(Counter(r["question_type"] for r in recs)))
    print("  sets:", len({r["set_id"] for r in recs if r["set_id"]}))
    missing = [r["source_id"] for r in recs
               if r["question_type"] == "mcsc" and not r.get("correct_answer")]
    print("  mcsc missing key:", missing)


if __name__ == "__main__":
    main()
