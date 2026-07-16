#!/usr/bin/env python3
"""Parse assignment .docx files into structured questions.

A .docx is a zip of XML — no python-docx dependency needed. Handles the
"Section A/B/C – ... (N Marks Each)" + "Qn. <text>" layout used by these
assignments. Emits questions with a heuristic qtype for review.

Usage:
    python parse_docx.py <file.docx> [<file2.docx> ...] --subject DAA
    python parse_docx.py samples/DAA_Assignment.docx --subject DAA --out out/daa.json
"""

import argparse
import html
import json
import re
import sys
import zipfile
from pathlib import Path

QTYPES = ("concept", "solve", "proof", "diagram", "predict_output", "program")

# Marks per section header, e.g. "Section B – Descriptive Questions (7 Marks Each)".
_SECTION_RE = re.compile(r"Section\s+([A-Z]).*?\((\d+)\s*Marks?", re.I)
# Question start, e.g. "Q7. Solve the recurrence ...".
_QUESTION_RE = re.compile(r"^Q\s*(\d+)\s*[\.\)]\s*(.+)$", re.S)


def docx_paragraphs(path: str) -> list[str]:
    """Return non-empty text paragraphs from a .docx in document order."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    paras = []
    for block in re.split(r"</w:p>", xml):
        runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", block, re.S)
        text = html.unescape("".join(runs)).strip()
        if text:
            paras.append(text)
    return paras


def guess_qtype(text: str) -> str:
    """Heuristic qtype — a draft the human review step corrects.

    Order matters: more specific signals win. A question that both explains a
    topic AND asks for a concrete computation (e.g. "Explain ... Construct the DP
    table for ...") is a `solve` — the marks are in the worked result.
    """
    t = text.lower()
    if "predict" in t and "output" in t:
        return "predict_output"
    if re.search(r"write a[n]? .{0,20}program|write .{0,20}code", t):
        return "program"
    if re.search(r"\bprove\b|show that|derive that", t):
        return "proof"
    # A concrete worked computation anywhere in the prompt → solve (checked before
    # the diagram/concept fallbacks so "Explain ... Solve/Construct ..." lands here).
    if re.search(
        r"\bsolve\s*(the |for |:)|^solve\b"       # imperative "solve", not passive "solved"
        r"|\b(comput|calculat|evaluat|determine|obtain)\w*\b"
        r"|find(ing)? the (max|min|lcs|shortest|optimal|value|minimum|longest)"
        r"|construct the (dp|table)|dp table for|minimum number of"
        r"|for:? (weights?|profit|frequenc)",
        t,
    ):
        return "solve"
    if re.search(
        r"\bdraw\b|construct (a|the) (dfa|nfa|pda|automat|state diagram|transition)"
        r"|state[- ]space tree|transition diagram",
        t,
    ):
        return "diagram"
    return "concept"


def extract_questions(paragraphs: list[str]) -> list[dict]:
    """Walk paragraphs, tracking the current section's marks, collecting questions.

    Multi-paragraph questions are joined until the next 'Qn.' or section header.
    """
    questions: list[dict] = []
    current_marks: int | None = None
    current_section: str | None = None
    position = 0

    def flush(buf: list[str]):
        nonlocal position
        if not buf:
            return
        text = " ".join(buf).strip()
        m = _QUESTION_RE.match(text)
        if not m:
            return
        body = m.group(2).strip()
        position += 1
        questions.append({
            "section": current_section,
            "marks": current_marks,
            "qtype": guess_qtype(body),
            "text": body,
            "position": position,
        })

    buf: list[str] = []
    for para in paragraphs:
        sec = _SECTION_RE.search(para)
        if sec:
            flush(buf); buf = []
            current_section = sec.group(1).upper()
            current_marks = int(sec.group(2))
            continue
        if _QUESTION_RE.match(para):
            flush(buf); buf = []
            buf = [para]
        elif buf:
            buf.append(para)  # continuation of the current question
    flush(buf)
    return questions


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse assignment .docx into questions JSON")
    ap.add_argument("files", nargs="+", help="one or more .docx files (in order)")
    ap.add_argument("--subject", required=True, help="subject code, e.g. DAA")
    ap.add_argument("--out", help="write JSON here (default: stdout)")
    args = ap.parse_args()

    out = []
    for idx, f in enumerate(args.files, start=1):
        qs = extract_questions(docx_paragraphs(f))
        for q in qs:
            q["subject"] = args.subject
            q["assignment"] = idx
            q["source_file"] = Path(f).name
        out.extend(qs)

    payload = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(payload)
        print(f"wrote {len(out)} questions to {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
