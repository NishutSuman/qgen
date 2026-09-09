#!/usr/bin/env python3
"""
Expand assessment template IDs into their full questions (assess-production).

Confirmed traversal (4 hops):

    assessmenttemplates._id
      -> sectionTemplates[]                        (ObjectId list, ordered)
    sectiontemplates._id                           (title = section name)
      -> selectionConfigs[].value                  (QuestionSelectionConfig ids)
    questionselectionconfigs._id
      -> questionIds[]                             (pool of interchangeable Qs)
    questions._id
      -> content.body, options[], mcscAnswer, ...

Each selection config holds a POOL of interchangeable question variants; the live
exam serves one per config per candidate. For a question BANK we keep every
variant.

Usage
-----
    export MONGO_URI="mongodb+srv://..."
    ./.venv/bin/python extractQuestion.py <tid> [<tid> ...] -o questions.json
    ./.venv/bin/python extractQuestion.py --inspect <tid>
"""

import argparse
import json
import os
import sys

from pymongo import MongoClient

try:
    from bson import ObjectId
except ImportError:
    sys.exit("pip install pymongo")


# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
DB_NAME = "assess-production"

COL_TEMPLATES = "assessmenttemplates"
COL_SECTION_TEMPLATES = "sectiontemplates"
COL_SELECTION_CONFIGS = "questionselectionconfigs"
COL_QUESTIONS = "questions"

TEMPLATE_SECTIONS_FIELD = "sectionTemplates"     # template -> section-template ids
SECTION_CONFIGS_FIELD = "selectionConfigs"       # section -> [{value, ref}]
CONFIG_QUESTIONS_FIELD = "questionIds"           # config -> question ids
# --------------------------------------------------------------------------


def oid_variants(value):
    """Same id as both ObjectId and str so either storage style matches."""
    out = [value]
    if isinstance(value, str):
        try:
            out.append(ObjectId(value))
        except Exception:
            pass
    elif isinstance(value, ObjectId):
        out.append(str(value))
    return out


def all_variants(values):
    seen, out = set(), []
    for v in values:
        for variant in oid_variants(v):
            key = (type(variant).__name__, str(variant))
            if key not in seen:
                seen.add(key)
                out.append(variant)
    return out


def fetch_in_order(collection, ids, projection=None):
    """One $in query, re-sorted to match the incoming id order."""
    if not ids:
        return [], []
    docs = list(collection.find({"_id": {"$in": all_variants(ids)}}, projection))
    by_id = {str(d["_id"]): d for d in docs}
    ordered = [by_id[str(i)] for i in ids if str(i) in by_id]
    missing = [str(i) for i in ids if str(i) not in by_id]
    return ordered, missing


def config_ids(section):
    """selectionConfigs is [{value, ref, _id}] -> pull the .value ids in order."""
    out = []
    for item in section.get(SECTION_CONFIGS_FIELD) or []:
        if isinstance(item, dict) and "value" in item:
            out.append(item["value"])
        else:
            out.append(item)
    return out


def resolve_config_questions(db, config):
    """A selection config either lists explicit questionIds (fixed pool) or
    selects dynamically by tag (QA sections): tagRelationships = [{operator,
    items:[tagId]}] plus optional types/difficulties filters. Return the ordered
    list of matching question ids for either case."""
    explicit = config.get(CONFIG_QUESTIONS_FIELD) or []
    if explicit:
        return [str(i) for i in explicit]

    clauses = []
    for rel in config.get("tagRelationships") or []:
        items = rel.get("items") or []
        variants = all_variants(items)
        if not variants:
            continue
        if (rel.get("operator") or "or").lower() == "and":
            clauses.append({"$and": [{"tagRelationships": v} for v in
                                     all_variants(items)]})
        else:
            clauses.append({"tagRelationships": {"$in": variants}})
    if not clauses:
        return []

    query = {"$and": clauses} if len(clauses) > 1 else clauses[0]
    types = config.get("types") or []
    if types:
        query = {"$and": [query, {"type": {"$in": types}}]}
    difficulties = config.get("difficulties") or []
    if difficulties:
        query = {"$and": [query, {"difficulty": {"$in": difficulties}}]}

    return [str(d["_id"]) for d in db[COL_QUESTIONS].find(query, {"_id": 1})]


def normalize_question(q):
    """Flatten one raw question doc into a clean bank record."""
    content = q.get("content") or {}
    options = []
    correct_ids = set()
    mcsc = q.get("mcscAnswer")
    if mcsc is not None:
        correct_ids.add(str(mcsc))
    for m in q.get("mcmcAnswer") or []:
        correct_ids.add(str(m))

    for i, opt in enumerate(q.get("options") or [], 1):
        oid = str(opt.get("_id"))
        options.append({
            "n": i,
            "id": oid,
            "body": opt.get("body"),
            "is_correct": oid in correct_ids,
        })

    correct_positions = [o["n"] for o in options if o["is_correct"]]

    return {
        "question_id": str(q.get("_id")),
        "type": q.get("type"),
        "content_type": content.get("type"),
        "body": content.get("body"),
        "options": options,
        "correct_option_ids": sorted(correct_ids),
        "correct_positions": correct_positions,
        "fitb_answer": q.get("fitbAnswer"),
        "int_answer": q.get("intAnswer"),
        "float_answer": q.get("floatAnswer"),
        "difficulty": q.get("difficulty"),
        "prep_time": q.get("prepTime"),
        "explanation": q.get("answerExplanation"),
        "tag_relationships": q.get("tagRelationships"),
        "labels": q.get("labels"),
    }


def inspect(db, template_ids):
    tid = template_ids[0]
    t = db[COL_TEMPLATES].find_one({"_id": {"$in": oid_variants(tid)}})
    print(f"TEMPLATE {tid}: {(t or {}).get('title') or (t or {}).get('name')}")
    print("  meta:", json.dumps((t or {}).get("meta", {}), default=str)[:400])
    sec_ids = t.get(TEMPLATE_SECTIONS_FIELD) or []
    print(f"  sectionTemplates ({len(sec_ids)}):")
    sections, _ = fetch_in_order(db[COL_SECTION_TEMPLATES], sec_ids)
    for s in sections:
        cids = config_ids(s)
        configs, _ = fetch_in_order(db[COL_SELECTION_CONFIGS], cids)
        seen = set()
        for c in configs:
            seen.update(resolve_config_questions(db, c))
        print(f"    - {s.get('title')!r:35} {len(cids)} configs, {len(seen)} questions")


def extract(db, template_ids):
    result, warnings = [], []
    for tid in template_ids:
        t = db[COL_TEMPLATES].find_one({"_id": {"$in": oid_variants(tid)}})
        if not t:
            warnings.append(f"{tid}: template not found")
            continue

        sec_ids = t.get(TEMPLATE_SECTIONS_FIELD) or []
        sections, missing = fetch_in_order(db[COL_SECTION_TEMPLATES], sec_ids)
        if missing:
            warnings.append(f"{tid}: section-templates not found -> {missing}")

        section_blocks = []
        for s in sections:
            cids = config_ids(s)
            configs, cmiss = fetch_in_order(db[COL_SELECTION_CONFIGS], cids)
            if cmiss:
                warnings.append(f"{tid}/{s.get('title')}: configs not found -> {cmiss}")

            qids, seen = [], set()
            for c in configs:
                for qid in resolve_config_questions(db, c):
                    if qid not in seen:
                        seen.add(qid)
                        qids.append(qid)

            questions, qmiss = fetch_in_order(db[COL_QUESTIONS], qids)
            if qmiss:
                warnings.append(f"{tid}/{s.get('title')}: questions not found -> {qmiss}")

            section_blocks.append({
                "section_id": str(s.get("_id")),
                "section_name": s.get("title") or s.get("name"),
                "config_count": len(configs),
                "question_count": len(questions),
                "questions": [normalize_question(q) for q in questions],
            })

        result.append({
            "template_id": str(tid),
            "template_name": t.get("title") or t.get("name"),
            "section_count": len(section_blocks),
            "total_questions": sum(b["question_count"] for b in section_blocks),
            "sections": section_blocks,
        })
    return result, warnings


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("template_ids", nargs="*")
    ap.add_argument("--ids-file")
    ap.add_argument("-o", "--output", default="questions.json")
    ap.add_argument("--uri", default=os.environ.get("MONGO_URI"))
    ap.add_argument("--db", default=DB_NAME)
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()

    if not args.uri:
        sys.exit("Set MONGO_URI or pass --uri")

    ids = list(args.template_ids)
    if args.ids_file:
        with open(args.ids_file) as fh:
            ids += [ln.strip() for ln in fh if ln.strip()]
    if not ids:
        sys.exit("Give at least one template id")

    db = MongoClient(args.uri)[args.db]

    if args.inspect:
        inspect(db, ids)
        return

    data, warnings = extract(db, ids)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, default=str)

    for block in data:
        print(f"{block['template_id']} {block['template_name']!r}: "
              f"{block['section_count']} sections, {block['total_questions']} questions")
        for s in block["sections"]:
            print(f"    {s['section_name']!r:35} {s['question_count']} Q")
    for w in warnings:
        print("WARN:", w, file=sys.stderr)
    print(f"\nWritten to {args.output}")


if __name__ == "__main__":
    main()
