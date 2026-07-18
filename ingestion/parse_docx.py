#!/usr/bin/env python3
"""Parse assignment files (.docx or .pdf) into structured questions.

Handles two layouts seen so far:
  A) "Section A – Descriptive Questions (7 Marks Each)"  +  "Qn. <text>"
  B) table / inline layout: "Section A/B/C" headers with
     "[CO tag] <n> <question text> <m> Marks" split across cells or lines.

Text extraction:
  .docx — zip+xml, pulls <w:t> runs from BOTH paragraphs and table cells
          (no python-docx dependency).
  .pdf  — pypdf (pip install pypdf).

qtype is a heuristic draft; the human review step corrects it.

Usage:
    python parse_docx.py <file1> [<file2> ...] --subject AJAVA [--out out.json]
"""

from __future__ import annotations  # lazy annotations — allow `X | None` on Python 3.9

import argparse
import html
import json
import re
import sys
import zipfile
from pathlib import Path

_SECTION_HDR = re.compile(r"Section\s+([A-Z])\b", re.I)
_SECTION_MARKS = re.compile(r"\((\d+)\s*Marks?", re.I)
_QN_DOT = re.compile(r"^Q\s*(\d+)\s*[\.\)]\s*(.+)$", re.S)   # layout A: "Q7. ..."
_MARKS_TOKEN = re.compile(r"(\d+)\s*Marks?\s*$", re.I)        # trailing "7 Marks"
_CO_TAG = re.compile(r"^\[?\s*CO\s*\d+\s*\]?$", re.I)          # "[CO3]"
_BARE_NUM = re.compile(r"^\d+$")


def _docx_lines(path: str) -> list[str]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    xml = xml.replace("<w:tab/>", "\t").replace("<w:br/>", "\n")
    # Emit text runs; treat paragraph and table-cell ends as line breaks.
    out: list[str] = []
    # [^<]* keeps each capture to a single text run — never spans across markup.
    for t, p_end, c_end in re.findall(
        r"<w:t[^>]*>([^<]*)</w:t>|(</w:p>)|(</w:tc>)", xml, re.S
    ):
        if t:
            out.append(html.unescape(t))
        elif p_end or c_end:
            out.append("\n")
    lines = [ln.strip() for ln in "".join(out).split("\n")]
    return [ln for ln in lines if ln]


def _pdf_lines(path: str) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        # RuntimeError (not sys.exit) so a library caller like dashboard.py can
        # catch it and return a clean error instead of dropping the connection.
        raise RuntimeError("pypdf not installed — run: pip install pypdf")
    reader = PdfReader(path)
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def extract_lines(path: str) -> list[str]:
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return _docx_lines(path)
    if suffix == ".pdf":
        return _pdf_lines(path)
    sys.exit(f"unsupported file type: {suffix}")


def guess_qtype(text: str) -> str:
    """Heuristic qtype — a draft the human review step corrects."""
    t = text.lower()
    if "predict" in t and "output" in t:
        return "predict_output"
    if re.search(r"write a[n]? .{0,25}program|write .{0,20}code", t):
        return "program"
    if re.search(r"\bprove\b|show that|derive that", t):
        return "proof"
    if re.search(
        r"\bsolve\s*(the |for |:)|^solve\b"
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


def _clean_question(text: str) -> str:
    text = _MARKS_TOKEN.sub("", text).strip()          # drop trailing "N Marks"
    text = re.sub(r"^\[?\s*CO\s*\d+\s*\]?\s*", "", text, flags=re.I)  # drop leading CO tag
    text = re.sub(r"^\d+[\.\)]?(\s+|(?=[A-Z]))", "", text)  # drop leading item number (fused or spaced)
    return text.strip()


def extract_questions(lines: list[str]) -> list[dict]:
    """Detect questions across both layouts.

    Layout A: a line matches "Qn. ...". Layout B: a question is the text that ends
    at a "N Marks" token (marks inline), or, if marks are only in the section header,
    a substantial line that isn't a CO tag / bare number / section header.
    """
    questions: list[dict] = []
    section: str | None = None
    section_marks: int | None = None
    position = 0
    buf: list[str] = []

    def is_noise(ln: str) -> bool:
        return bool(_CO_TAG.match(ln) or _BARE_NUM.match(ln))

    def flush(marks: int | None):
        nonlocal position
        text = _clean_question(" ".join(buf)).strip()
        buf.clear()
        if len(text) < 6:   # not a real question
            return
        position += 1
        questions.append({
            "section": section,
            "marks": marks if marks is not None else section_marks,
            "qtype": guess_qtype(text),
            "text": text,
            "position": position,
        })

    for ln in lines:
        hdr = _SECTION_HDR.search(ln)
        if hdr and len(ln) < 60:   # a section header line, not prose mentioning "section"
            if buf:
                flush(None)
            section = hdr.group(1).upper()
            m = _SECTION_MARKS.search(ln)
            section_marks = int(m.group(1)) if m else None
            continue

        m = _QN_DOT.match(ln)      # layout A
        if m:
            if buf:
                flush(None)
            buf.append(m.group(2))
            continue

        marks_here = _MARKS_TOKEN.search(ln)   # layout B: marks close a question
        if marks_here:
            body = _MARKS_TOKEN.sub("", ln).strip()
            if body and not is_noise(body):
                buf.append(body)
            if buf:
                flush(int(marks_here.group(1)))
            continue

        if is_noise(ln):
            # CO tag / bare number: boundary between questions in table layout
            if buf and _QN_DOT_boundary(buf):
                flush(None)
            continue

        if section is None:
            continue   # skip document preamble before the first "Section" header
        buf.append(ln)

    if buf:
        flush(None)
    return questions


def _QN_DOT_boundary(buf: list[str]) -> bool:
    # In table layout a CO tag starts a new row; flush the accumulated question
    # only if it already looks complete (ends with punctuation).
    return bool(buf) and buf[-1].rstrip().endswith((".", "?", ":"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse assignment files into questions JSON")
    ap.add_argument("files", nargs="+", help="one or more .docx / .pdf files (in order)")
    ap.add_argument("--subject", required=True, help="subject code, e.g. AJAVA")
    ap.add_argument("--out", help="write JSON here (default: stdout)")
    args = ap.parse_args()

    out = []
    for idx, f in enumerate(args.files, start=1):
        qs = extract_questions(extract_lines(f))
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
