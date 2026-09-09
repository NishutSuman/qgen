#!/usr/bin/env python3
"""imat_export_pdf.py — institute verification PDF (reportlab).

A curated, exam-style PDF generated from the SAME source as the upload CSV
(work/imat/questions.json): cover page with exam metadata + marking scheme +
instructions, then each section with its sets (passage / markdown table / chart
image shown ONCE per set) and questions, each with options, the marked correct
answer, and the solution — for human verification before upload.

Requires reportlab + matplotlib charts already rendered. Run with the venv:
    .venv/bin/python scripts/imat_export_pdf.py --in work/imat/questions.json \
        --out output/imat_paper.pdf --title "IIT Jodhpur Qualifier - BS" \
        --blueprints imat/blueprints.json
"""
import argparse
import json
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from imat_render import diff_label

NAVY = colors.HexColor("#1a3c6e")
GREEN = colors.HexColor("#0a6b2e")
GREY = colors.HexColor("#555555")
LETTER = "ABCDE"


import re


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def md_inline(text):
    """Escape, then render **bold** and convert blank lines/newlines into
    paragraph breaks. Returns a list of (html, is_block) paragraph strings."""
    paras = []
    for block in (text or "").split("\n\n"):
        block = block.strip()
        if not block:
            continue
        html = esc(block)
        html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
        html = html.replace("\n", "<br/>")
        paras.append(html)
    return paras


def styles():
    ss = getSampleStyleSheet()
    out = {
        "title": ParagraphStyle("t", parent=ss["Title"], textColor=NAVY, fontSize=20, spaceAfter=4),
        "sub": ParagraphStyle("s", parent=ss["Normal"], alignment=TA_CENTER, fontSize=11,
                              textColor=colors.HexColor("#b03030"), spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], textColor=NAVY, fontSize=12, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=13),
        "just": ParagraphStyle("j", parent=ss["Normal"], fontSize=9.5, leading=13, alignment=TA_JUSTIFY),
        "qnum": ParagraphStyle("q", parent=ss["Normal"], fontSize=10, leading=13, spaceBefore=6),
        "opt": ParagraphStyle("o", parent=ss["Normal"], fontSize=9.5, leading=13, leftIndent=14),
        "optok": ParagraphStyle("ok", parent=ss["Normal"], fontSize=9.5, leading=13, leftIndent=14,
                                textColor=GREEN),
        "ans": ParagraphStyle("a", parent=ss["Normal"], fontSize=9, leading=12, textColor=GREEN, leftIndent=14),
        "sol": ParagraphStyle("sol", parent=ss["Normal"], fontSize=8.5, leading=11, textColor=GREY, leftIndent=14),
        "instr": ParagraphStyle("i", parent=ss["Normal"], fontSize=9, leading=12, textColor=GREY, spaceBefore=4),
        "bullet": ParagraphStyle("bu", parent=ss["Normal"], fontSize=9.5, leading=13, leftIndent=10, bulletIndent=0),
        "sectionbar": ParagraphStyle("sb", parent=ss["Normal"], fontSize=13, textColor=colors.white,
                                     fontName="Helvetica-Bold"),
    }
    return out


def md_to_flowables(md, st):
    """Render a stimulus markdown string (paragraphs + pipe tables) to flowables."""
    flow = []
    blocks = [b for b in md.split("\n\n")]
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        table_lines = [ln for ln in lines if ln.strip().startswith("|")]
        if len(table_lines) >= 2:
            # caption lines before the table
            for ln in lines:
                if ln.strip().startswith("|"):
                    break
                flow.append(Paragraph(esc(ln), st["body"]))
            rows = []
            for ln in table_lines:
                cells = [c.strip() for c in ln.strip().strip("|").split("|")]
                if all(set(c) <= set("-: ") for c in cells):   # separator row
                    continue
                rows.append([Paragraph(esc(c), st["body"]) for c in cells])
            if rows:
                t = Table(rows, hAlign="LEFT")
                t.setStyle(TableStyle([
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f8")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                flow.append(t)
        else:
            flow.append(Paragraph(esc(block.replace("\n", " ")), st["just"]))
        flow.append(Spacer(1, 3))
    return flow


def section_bar(text, st):
    t = Table([[Paragraph(esc(text), st["sectionbar"])]], colWidths=[170 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t


def cover_pattern(story, st, title, qs, pattern):
    """Cover for a QUESTION BANK: the exam is described by a fixed TEST PATTERN
    (sections, per-section time, questions-per-test, marks) that is independent of
    how many questions the bank holds. A test draws from the bank following this
    pattern, so marks/time come from the pattern, not from len(qs)."""
    from collections import Counter
    order = pattern.get("section_order") or ["VARC", "DILR", "QA"]
    pq = pattern.get("pattern_questions", {})
    secmin = pattern.get("section_minutes", {})
    per_correct = pattern.get("marks_per_correct", 3)
    n_test = sum(pq.get(s, 0) for s in order)
    max_marks = per_correct * n_test
    dur = pattern.get("duration_min", 60)
    dur_str = (f"{dur // 60} Hour" + ("" if dur // 60 == 1 else "s")) if dur % 60 == 0 else f"{dur} minutes"
    mk = pattern.get("marking", {})
    mcq, tita = mk.get("mcq", {}), mk.get("tita", {})
    bank = Counter(q["section"] for q in qs)

    story.append(Paragraph(esc(title), st["title"]))
    story.append(Paragraph(f"Time: {dur_str} &nbsp;|&nbsp; Maximum Marks: {max_marks}", st["sub"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Test Pattern", st["h2"]))
    if pattern.get("note"):
        story.append(Paragraph(f"<i>{esc(pattern['note'])}</i>", st["instr"]))
    for s in order:
        story.append(Paragraph(f"&bull; <b>{s}</b>: {pq.get(s, 0)} questions &nbsp;|&nbsp; "
                               f"{secmin.get(s, dur // max(1, len(order)))} min", st["bullet"]))
    story.append(Paragraph(f"&bull; <b>Total</b>: {n_test} questions across {len(order)} sections "
                           f"&nbsp;|&nbsp; Duration {dur_str} &nbsp;|&nbsp; Maximum Marks {max_marks}",
                           st["bullet"]))

    story.append(Paragraph("Marking Scheme", st["h2"]))
    story.append(Paragraph(f"&bull; MCQ: +{mcq.get('correct', 3)} for a correct answer, "
                           f"{mcq.get('wrong', -1)} for a wrong answer.", st["bullet"]))
    story.append(Paragraph(f"&bull; TITA / Non-MCQ: +{tita.get('correct', 3)} for a correct answer, "
                           f"no negative marking.", st["bullet"]))
    story.append(Paragraph("&bull; Unanswered questions: no marks awarded or deducted.", st["bullet"]))

    story.append(Paragraph("General Instructions", st["h2"]))
    per = secmin.get(order[0], dur // max(1, len(order)))
    same_time = len({secmin.get(s, per) for s in order}) == 1
    time_line = (f"Each section is allotted {per} minutes; the total duration is {dur_str}."
                 if same_time else f"Per-section times are shown above; total duration is {dur_str}.")
    for line in ["Read each question carefully before attempting.",
                 "For MCQs, choose the single most appropriate option (A-D, or A-E where shown).",
                 "For TITA questions, type the final numerical answer.",
                 time_line,
                 "Attempt the sections in the given order and manage your time across all sections."]:
        story.append(Paragraph(f"&bull; {esc(line)}", st["bullet"]))
    story.append(Spacer(1, 6))
    variants = [v for v in ("MBA", "BS") if any(q.get("variant") == v for q in qs)]
    if variants:
        parts = []
        for v in variants:
            vc = Counter(q["section"] for q in qs if q.get("variant") == v)
            parts.append(f"{v} {sum(vc.values())} ("
                         + "/".join(f"{vc[s]} {s}" for s in order if s in vc) + ")")
        breakdown = "; ".join(parts)
    else:
        breakdown = ", ".join(f"{bank[s]} {s}" for s in order if s in bank)
    story.append(Paragraph(f"<i>This question bank holds {len(qs)} questions -- {breakdown}. "
                           f"Each test is assembled from it following the pattern above. "
                           f"Correct option shown in green.</i>", st["instr"]))
    story.append(Spacer(1, 8))


def cover(story, st, title, qs, exam):
    n = len(qs)
    from collections import Counter
    secs = Counter(q["section"] for q in qs)
    n_mcq = sum(1 for q in qs if q["question_type"] == "mcsc")
    n_tita = sum(1 for q in qs if q["question_type"] == "tita")
    max_marks = exam.get("marks_per_correct", 3) * n
    dur = exam.get("duration_min", 120)
    secmin = exam.get("section_minutes", {})
    mk = exam.get("marking", {})
    mcq, tita = mk.get("mcq", {}), mk.get("tita", {})
    # human-friendly duration ("1 Hour", "90 minutes", "2 Hours")
    if dur % 60 == 0:
        h = dur // 60
        dur_str = f"{h} Hour" + ("" if h == 1 else "s")
    else:
        dur_str = f"{dur} minutes"

    story.append(Paragraph(esc(title), st["title"]))
    story.append(Paragraph(f"Time: {dur_str} &nbsp;|&nbsp; Maximum Marks: {max_marks}",
                           st["sub"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Question Distribution", st["h2"]))
    for s in exam.get("section_order", list(secs)):
        if s in secs:
            mins = secmin.get(s, dur // max(1, len(secs)))
            story.append(Paragraph(f"&bull; <b>{s}</b>: {secs[s]} questions &nbsp;"
                                   f"(suggested time {mins} min)", st["bullet"]))
    story.append(Paragraph(f"&bull; Total: {n} questions &nbsp;|&nbsp; MCQ {n_mcq} "
                           f"&nbsp;|&nbsp; TITA (non-MCQ) {n_tita}", st["bullet"]))

    story.append(Paragraph("Marking Scheme", st["h2"]))
    story.append(Paragraph(f"&bull; MCQ: +{mcq.get('correct',3)} for a correct answer, "
                           f"{mcq.get('wrong',-1)} for a wrong answer.", st["bullet"]))
    if n_tita:
        story.append(Paragraph(f"&bull; TITA / Non-MCQ: +{tita.get('correct',3)} for a correct "
                               f"answer, no negative marking.", st["bullet"]))
    story.append(Paragraph("&bull; Unanswered questions: no marks awarded or deducted.", st["bullet"]))

    story.append(Paragraph("General Instructions", st["h2"]))
    instr = ["Read each question carefully before attempting.",
             "For MCQs, choose the single most appropriate option (A-D, or A-E where shown)."]
    if n_tita:
        instr.append("For TITA questions, type the final numerical answer.")
    instr += [
        f"Total duration is {dur_str}; the suggested per-section times are shown above.",
        "Sections may be attempted in any order; manage your time across all sections.",
    ]
    for line in instr:
        story.append(Paragraph(f"&bull; {esc(line)}", st["bullet"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<i>This is the answer-marked verification copy (correct option in green, "
                           "with solution) and mirrors the content of the upload CSV.</i>", st["instr"]))
    story.append(Spacer(1, 8))   # flow straight into the first section (no wasted page)


def render_question(q, st, asset_root):
    flow = []
    tag = (f"<b>Q{q['question_id']}.</b> <font size=7 color='#888888'>"
           f"[{esc(q['set_id'])} &middot; {q['question_type']} &middot; "
           f"diff {diff_label(q['difficulty'])}]</font>")
    flow.append(Paragraph(tag, st["qnum"]))
    # question text may carry its own paragraph structure (instruction / body /
    # **bold question**) — render each block as its own spaced paragraph.
    for i, para in enumerate(md_inline(q.get("question_text", ""))):
        flow.append(Paragraph(para, st["body"]))
        flow.append(Spacer(1, 2))
    if q["question_type"] == "mcsc":
        ca = str(q.get("correct_answer"))
        for i in range(1, q["num_options"] + 1):
            k = str(i)
            opt = (q.get("options") or {}).get(k, "")
            mark = " &#10003;" if k == ca else ""
            style = st["optok"] if k == ca else st["opt"]
            flow.append(Paragraph(f"{LETTER[i-1]}) {esc(opt)}{mark}", style))
        flow.append(Paragraph(f"<b>Answer: {LETTER[int(ca)-1]})</b> "
                              f"{esc((q.get('options') or {}).get(ca,''))}", st["ans"]))
    else:
        flow.append(Paragraph(f"<b>Answer (TITA):</b> {esc(q.get('tita_answer',''))}", st["ans"]))
    if q.get("explanation"):
        flow.append(Paragraph(f"<b>Solution:</b> {esc(q['explanation'])}", st["sol"]))
    flow.append(Spacer(1, 4))
    return KeepTogether(flow)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="work/imat/questions.json")
    ap.add_argument("--out", default="output/imat_paper.pdf")
    ap.add_argument("--title", default="IMAT Qualifier - Verification Paper")
    ap.add_argument("--blueprints", default="imat/blueprints.json")
    ap.add_argument("--paper", default=None,
                    help="variant key; uses its exam block (duration/marking/sections) if present")
    ap.add_argument("--pattern", default=None,
                    help="JSON file describing a fixed TEST PATTERN for a question bank "
                         "(cover marks/time come from the pattern, not the bank size)")
    args = ap.parse_args()

    with open(args.inp, encoding="utf-8") as f:
        qs = json.load(f)
    pattern = None
    if args.pattern and os.path.exists(args.pattern):
        with open(args.pattern, encoding="utf-8") as f:
            pattern = json.load(f)
    exam = {}
    if os.path.exists(args.blueprints):
        with open(args.blueprints, encoding="utf-8") as f:
            bp = json.load(f)
        variant = (bp.get("variants") or {}).get(args.paper or "", {})
        exam = variant.get("exam") or bp.get("exam", {})
    asset_root = os.path.dirname(args.out) or "."
    st = styles()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(18 * mm, 10 * mm, "Confidential - For Examination Use Only")
        canvas.drawRightString(195 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(args.out, pagesize=A4, topMargin=16 * mm, bottomMargin=16 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm, title=args.title)
    story = []
    if pattern:
        cover_pattern(story, st, args.title, qs, pattern)
    else:
        cover(story, st, args.title, qs, exam)

    sec_minutes = (pattern or {}).get("section_minutes") or exam.get("section_minutes", {})
    # `band` groups the body (e.g. "MBA — VARC"); falls back to plain section.
    cur_band, cur_set = None, None
    for q in qs:
        band = q.get("band") or q["section"]
        if band != cur_band:
            cur_band = band
            secmin = sec_minutes.get(q["section"])
            label = f"Section: {band}" + (f"   ({secmin} min)" if secmin else "")
            story.append(Spacer(1, 6))
            story.append(section_bar(label, st))
            story.append(Spacer(1, 4))
        if q.get("shared_set") and q["set_id"] != cur_set:
            cur_set = q["set_id"]
            story.append(Paragraph(
                f"<b>Instructions ({q['set_id']}):</b> study the shared "
                f"{'passage' if q['kind']=='passage' else 'data'} below and answer its "
                f"{q['set_size']} question(s).", st["instr"]))
            s = q.get("stimulus") or {}
            if s.get("markdown"):
                for fl in md_to_flowables(s["markdown"], st):
                    story.append(fl)
            for img in s.get("images") or []:
                p = os.path.join(asset_root, img)
                if os.path.exists(p):
                    story.append(Image(p, width=150 * mm, height=84 * mm, kind="proportional"))
                    story.append(Spacer(1, 3))
        story.append(render_question(q, st, asset_root))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"[OK] wrote verification PDF ({len(qs)} questions) -> {args.out}")


if __name__ == "__main__":
    main()
