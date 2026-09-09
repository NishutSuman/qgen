#!/usr/bin/env python3
"""imat_render.py — shared rendering helpers for IMAT export.

Both imat_export_csv.py and imat_export_pdf.py import these so the CSV and the
verification PDF are generated from the SAME source and stay byte-for-byte
consistent in content (the institute verifies exactly what is uploaded).
"""
import re

_INT_RE = re.compile(r"^-?\d+$")


def compose_body(q):
    """The self-contained content shown to the student: instruction + stimulus + prompt.

    The stimulus (passage / markdown table / chart image) is attached to EVERY
    question of a set, so each uploaded question stands alone. The blueprint's
    set-level `instruction` is prepended for the same reason: on the platform a
    candidate sees one question at a time, so it must state what to do with the
    block above. Standalone single questions (QA, GA) carry no instruction.

    This is the CSV body only — the PDF prints its own per-set instruction line.
    """
    s = q.get("stimulus") or {}
    parts = []
    instr = (q.get("instruction") or "").strip()
    if instr:
        parts.append(instr)
    md = (s.get("markdown") or "").strip()
    if md:
        parts.append(md)
    # Prefer the uploaded S3 URLs (so the platform link is baked into every
    # question of the set); fall back to local paths before upload.
    for img in (s.get("image_urls") or s.get("images") or []):
        parts.append(f"![chart]({img})")
    prompt = (q.get("question_text") or "").strip()
    if prompt:
        parts.append(prompt)
    return "\n\n".join(parts)


def is_markdown(body):
    return bool(re.search(r"\$|\||!\[|\\frac|\\sqrt|\^\{|_\{", body or ""))


def answer_fields(q):
    """Return (mcscAnswer, intAnswer, fitbAnswer) for the CSV."""
    if q.get("question_type") == "mcsc":
        return str(q.get("correct_answer", "")), "", ""
    ans = str(q.get("tita_answer", "")).strip()
    if _INT_RE.match(ans):
        return "", ans, ""
    return "", "", ans


def option_cells(q, max_opts=5):
    opts = q.get("options") or {}
    return [opts.get(str(i), "") for i in range(1, max_opts + 1)]


def diff_label(d):
    return {0: "0", 0.0: "0", 0.5: "0.5", 1: "1", 1.0: "1"}.get(d, str(d))
