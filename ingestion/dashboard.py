#!/usr/bin/env python3
"""TutorBank Mac dashboard (CLAUDE.md §7 Mac tool, extends the M4 review tool).

Local, localhost-only web app to MANAGE all content:
  - browse the subject → unit → question → answer tree
  - add / edit / delete subjects, units, assignments, questions, answers
  - upload a .docx/.pdf assignment → parse → auto-generate exam answers with
    DeepSeek → render diagrams → insert (all from the browser)
  - review queue: unverified / low-confidence first, edit + flip `verified`

Run:
    cd ingestion && python3 dashboard.py      # opens http://127.0.0.1:8765

Stdlib only (+ the sibling parse_docx.py). Writes to Supabase with the
service-role key and generates with DeepSeek — both from ../.env. Do NOT expose
beyond localhost.
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import parse_docx  # sibling module

PORT = 8765
HERE = Path(__file__).resolve().parent
PROMPTS_DIR = HERE / "prompts"
SAMPLES_DIR = HERE / "samples"


def load_env() -> dict:
    env: dict[str, str] = {}
    path = HERE.parent / ".env"
    if not path.exists():
        raise SystemExit("missing ../.env")
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
        if not env.get(key):
            raise SystemExit(f"{key} missing from ../.env")
    return env


ENV = load_env()
SB_URL = ENV["SUPABASE_URL"].rstrip("/")
SVC = ENV["SUPABASE_SERVICE_KEY"]
DEEPSEEK_KEY = ENV.get("DEEPSEEK_API_KEY", "")
ACCESS_TOKEN = ENV.get("SUPABASE_ACCESS_TOKEN", "")
PROJECT_REF = ENV.get("SUPABASE_PROJECT_REF", "")
MODELS = json.loads((HERE.parent / "backend/supabase/functions/_shared/models.json").read_text())


# ---------------------------------------------------------------------------
# Supabase: PostgREST (data) + management API (transactional cascade deletes)
# ---------------------------------------------------------------------------

def sb(method: str, path: str, body=None, extra_headers: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"apikey": SVC, "Authorization": f"Bearer {SVC}",
               "Content-Type": "application/json", "User-Agent": "tutorbank-dash/1"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(f"{SB_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def sb_sql(query: str):
    """Run raw SQL via the management API (used for ordered cascade deletes)."""
    if not (ACCESS_TOKEN and PROJECT_REF):
        raise RuntimeError("SUPABASE_ACCESS_TOKEN / SUPABASE_PROJECT_REF needed for delete")
    body = json.dumps({"query": query}).encode()
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=body, method="POST",
        # A non-python User-Agent — Cloudflare 1010-blocks the default urllib UA.
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "curl/8"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


# Only these tables may be written through the generic create/update endpoints —
# stops a UI bug (or a page that somehow reached the API) from touching anything else.
WRITABLE = {"subjects", "units", "assignments", "questions", "answers"}


def insert_row(table: str, row: dict) -> dict:
    if table not in WRITABLE:
        raise ValueError(f"table {table} not writable")
    res = sb("POST", f"/rest/v1/{table}", body=row, extra_headers={"Prefer": "return=representation"})
    return (res or [{}])[0]


def patch_row(table: str, row_id: str, fields: dict) -> None:
    if table not in WRITABLE:
        raise ValueError(f"table {table} not writable")
    sb("PATCH", f"/rest/v1/{table}?id=eq.{urllib.parse.quote(row_id)}", body=fields,
       extra_headers={"Prefer": "return=minimal"})


def _q(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def delete_tree(kind: str, row_id: str) -> None:
    """Delete a node and everything under it, in FK-safe order (answers cascade
    from questions; questions.unit_id/assignment_id are ON DELETE SET NULL, so
    delete dependent questions explicitly to avoid orphans)."""
    i = _q(row_id)
    if kind == "subject":
        # Only delete THIS subject's own questions (by unit membership). Deleting
        # the subject cascades its units + assignments; a question in ANOTHER
        # subject that merely referenced one of this subject's assignments keeps
        # its unit and gets assignment_id set NULL (schema ON DELETE SET NULL) —
        # so it is never over-deleted.
        sb_sql(f"delete from questions where unit_id in (select id from units where subject_id={i}); "
               f"delete from subjects where id={i};")
    elif kind == "unit":
        # Questions belong to their unit — deleting the unit deletes them (intended).
        sb_sql(f"delete from questions where unit_id={i}; delete from units where id={i};")
    elif kind == "assignment":
        # An assignment is only provenance; its questions live under units. Just
        # remove the assignment — the cascade nulls questions.assignment_id, keeping
        # the questions in their units (don't hard-delete them from their unit).
        sb_sql(f"delete from assignments where id={i};")
    elif kind == "question":
        sb_sql(f"delete from questions where id={i};")
    elif kind == "answer":
        sb_sql(f"delete from answers where id={i};")
    else:
        raise ValueError(f"unknown delete kind {kind}")


# ---------------------------------------------------------------------------
# LaTeX → Unicode cleanup (DeepSeek still emits LaTeX; mirror mathtext.ts).
# Leaves ```-fenced code untouched so escapes like \n aren't mangled.
# ---------------------------------------------------------------------------

_SYM = {
    r"\cdot": "·", r"\times": "×", r"\div": "÷", r"\pm": "±", r"\leq": "≤", r"\le": "≤",
    r"\geq": "≥", r"\ge": "≥", r"\neq": "≠", r"\ne": "≠", r"\approx": "≈", r"\to": "→",
    r"\rightarrow": "→", r"\Rightarrow": "⇒", r"\infty": "∞", r"\int": "∫", r"\sum": "Σ",
    r"\prod": "∏", r"\sqrt": "√", r"\partial": "∂", r"\in": "∈", r"\forall": "∀",
    r"\exists": "∃", r"\alpha": "α", r"\beta": "β", r"\gamma": "γ", r"\delta": "δ",
    r"\epsilon": "ε", r"\theta": "θ", r"\lambda": "λ", r"\mu": "μ", r"\pi": "π",
    r"\sigma": "σ", r"\phi": "φ", r"\omega": "ω", r"\Delta": "Δ", r"\Sigma": "Σ", r"\Omega": "Ω",
}
_SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷",
        "8": "⁸", "9": "⁹", "n": "ⁿ", "x": "ˣ", "+": "⁺", "-": "⁻", "i": "ⁱ"}
_SUB = {"0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆", "7": "₇",
        "8": "₈", "9": "₉", "n": "ₙ", "i": "ᵢ", "j": "ⱼ"}


def _convert(s: str) -> str:
    # NB: do NOT blanket-strip { } — braces are legitimate content in FLAT/DAA
    # (set notation {aⁿbⁿ}, grammars {S→aSb}). Only remove braces that belong to
    # the specific LaTeX constructs handled below.
    s = re.sub(r"\$\$?", "", s)  # $ / $$ math delimiters
    s = re.sub(r"\\(?:boxed|text|mathrm|mathbf|operatorname)\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\left|\\right", "", s)
    s = re.sub(r"\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"(\1)/(\2)", s)
    for k, v in _SYM.items():
        s = s.replace(k, v)
    s = re.sub(r"\^\{([0-9nxi+\-]+)\}", lambda m: "".join(_SUP.get(c, "^" + c) for c in m.group(1)), s)
    s = re.sub(r"\^([0-9nxi+\-])", lambda m: _SUP.get(m.group(1), "^" + m.group(1)), s)
    s = re.sub(r"_\{([0-9nij]+)\}", lambda m: "".join(_SUB.get(c, "_" + c) for c in m.group(1)), s)
    s = re.sub(r"_([0-9nij])", lambda m: _SUB.get(m.group(1), "_" + m.group(1)), s)
    s = re.sub(r"\\([a-zA-Z]+)", r"\1", s)  # strip backslash before leftover word commands
    return s


def unicode_summary(s: str) -> str:
    return re.sub(r"\s+", " ", _convert(s or "")).strip()


def unicode_answer(s: str) -> str:
    parts = (s or "").split("```")
    return "```".join(p if i % 2 else _convert(p) for i, p in enumerate(parts))


# ---------------------------------------------------------------------------
# DeepSeek generation + Graphviz rendering
# ---------------------------------------------------------------------------

def deepseek(messages: list, model: str) -> str:
    if not DEEPSEEK_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY not set in ../.env")
    body = json.dumps({"model": model, "messages": messages, "stream": False,
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(f"{MODELS['base_url']}/chat/completions", data=body, method="POST",
                                 headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def subject_prompt(subject: dict) -> str:
    """Per-subject generation rules: prefer the DB format_profile, fall back to
    the prompts/<CODE>.md file, else nothing."""
    fp = subject.get("format_profile") or {}
    if isinstance(fp, dict) and fp.get("prompt"):
        return fp["prompt"]
    f = PROMPTS_DIR / f"{subject.get('code', '')}.md"
    return f.read_text() if f.exists() else ""


def generate_answer(qtext: str, qtype: str, subject: dict, marks=None) -> dict:
    base = (PROMPTS_DIR / "base.md").read_text()
    system = base + "\n\n" + subject_prompt(subject)
    mk = f"This is a {marks}-mark " if marks else "This is a "
    user = (f"{mk}{qtype} question. Answer it exactly as this system produces, "
            f"returning the JSON fields.\nQUESTION: {qtext}")
    content = deepseek([{"role": "system", "content": system},
                        {"role": "user", "content": user}], MODELS["accurate"])
    try:
        data = json.loads(content)
    except Exception:
        m = re.search(r"\{.*\}", content, re.S)
        data = json.loads(m.group(0)) if m else {}
    summary = unicode_summary(data.get("summary", ""))
    answer = unicode_answer(data.get("answer", ""))
    if not summary and not answer:
        raise RuntimeError("empty model reply")
    return {
        "summary": summary,
        "answer": answer,
        "final_answer": data.get("final_answer"),
        "diagram_dot": data.get("diagram_dot"),
        # Coerce to the [{q,a}] shape the watch (Bank.swift) decodes — one bad
        # followup would otherwise fail the decode of the ENTIRE /sync payload.
        "followups": _clean_followups(data.get("followups")),
        # The schema check-constrains confidence to [0,1]; the model sometimes
        # returns 95 or "high" — clamp/nullify so the insert can't be rejected.
        "confidence": _clamp_confidence(data.get("confidence")),
    }


def _clean_followups(fu) -> list:
    out = []
    for x in fu or []:
        if isinstance(x, dict) and isinstance(x.get("q"), str) and isinstance(x.get("a"), str):
            out.append({"q": x["q"], "a": x["a"]})
    return out


def _clamp_confidence(c):
    try:
        v = float(c)
    except (TypeError, ValueError):
        return None
    return v if 0.0 <= v <= 1.0 else None


def upload_png(path_in_bucket: str, data: bytes) -> None:
    req = urllib.request.Request(f"{SB_URL}/storage/v1/object/diagrams/{path_in_bucket}",
                                 data=data, method="POST",
                                 headers={"Authorization": f"Bearer {SVC}", "apikey": SVC,
                                          "Content-Type": "image/png", "x-upsert": "true",
                                          "User-Agent": "tutorbank-dash/1"})
    urllib.request.urlopen(req, timeout=30).read()


def render_diagram(answer_id: str, dot: str) -> bool:
    """DOT → watch PNG + hi-res detail PNG → storage (CLAUDE.md §6). Best-effort."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "g.dot").write_text(dot)
        full = d / "full.png"
        watch = d / "watch.png"
        r = subprocess.run(["dot", "-Tpng", "-Gdpi=200", "-Gbgcolor=white", "-Nfontname=Helvetica",
                            "-Nfontsize=20", "-Npenwidth=2", "-Ncolor=black", "-Epenwidth=1.8",
                            str(d / "g.dot"), "-o", str(full)], capture_output=True, text=True)
        if r.returncode != 0 or not full.exists():
            return False
        subprocess.run(["sips", "--resampleWidth", "736", str(full), "--out", str(watch)],
                       capture_output=True)
        try:
            upload_png(f"watch/{answer_id}.png", watch.read_bytes())
            upload_png(f"phone/{answer_id}.png", full.read_bytes())
            return True
        except Exception:
            return False


def generate_for_question(question_id: str, marks=None) -> dict:
    """Fetch a question + its subject, generate an answer, render any diagram, and
    ATOMICALLY upsert the default answer. Generation happens BEFORE any DB write, so
    a failed generation never destroys the prior answer; the upsert (single request,
    on the unique(question_id,variant) constraint) then replaces it with no window
    where the question is left answerless."""
    select = ("id,text,qtype,unit:units!inner(subject:subjects!inner(id,code,name,format_profile))")
    rows = sb("GET", f"/rest/v1/questions?id=eq.{urllib.parse.quote(question_id)}&select={urllib.parse.quote(select)}")
    if not rows:
        raise RuntimeError("question not found")
    q = rows[0]
    subject = (q.get("unit") or {}).get("subject") or {}
    gen = generate_answer(q["text"], q["qtype"], subject, marks)  # may raise — nothing written yet

    # Upsert on (question_id, variant). Explicitly null the diagram paths so a
    # regenerate that no longer has a diagram can't leave a stale one pointing at
    # the old PNG; they get re-set below only if a fresh render succeeds.
    res = sb("POST", "/rest/v1/answers?on_conflict=question_id,variant",
             body={
                 "question_id": question_id, "variant": "default",
                 "summary": gen["summary"], "answer": gen["answer"], "final_answer": gen["final_answer"],
                 "diagram_dot": gen["diagram_dot"], "diagram_png_watch": None, "diagram_png_phone": None,
                 "followups": gen["followups"], "confidence": gen["confidence"],
                 "model_used": MODELS["accurate"], "verified": False,
             },
             extra_headers={"Prefer": "resolution=merge-duplicates,return=representation"})
    ans = (res or [{}])[0]
    if gen.get("diagram_dot") and ans.get("id"):
        if render_diagram(ans["id"], gen["diagram_dot"]):
            patch_row("answers", ans["id"],
                      {"diagram_png_watch": f"watch/{ans['id']}.png",
                       "diagram_png_phone": f"phone/{ans['id']}.png"})
    return {"answer_id": ans.get("id"), "summary": gen["summary"],
            "has_diagram": bool(gen.get("diagram_dot"))}


MAX_UPLOAD = 25 * 1024 * 1024  # 25 MB — assignments are small


def parse_upload(filename: str, raw: bytes) -> list[dict]:
    if len(raw) > MAX_UPLOAD:
        raise ValueError("file too large (max 25 MB)")
    SAMPLES_DIR.mkdir(exist_ok=True)
    # Path(...).name strips any directory part; the regex then keeps it to a plain
    # filename (belt and suspenders against path traversal via the upload name).
    safe = re.sub(r"[^A-Za-z0-9._ ()-]", "_", Path(filename).name) or "upload"
    dest = SAMPLES_DIR / safe
    dest.write_bytes(raw)
    lines = parse_docx.extract_lines(str(dest))
    questions = parse_docx.extract_questions(lines)
    for qn in questions:
        qn["source_file"] = safe
    return questions


# ---------------------------------------------------------------------------
# Reads for the UI
# ---------------------------------------------------------------------------

def fetch_tree() -> list[dict]:
    select = ("id,code,name,"
              "units(id,name,position,questions(id,text,qtype,position,"
              "answers(id,verified,confidence))),"
              "assignments(id,title,number)")
    subs = sb("GET", f"/rest/v1/subjects?select={urllib.parse.quote(select)}&order=code")
    for s in subs or []:
        s["units"] = sorted(s.get("units") or [], key=lambda u: u.get("position") or 0)
        for u in s["units"]:
            u["questions"] = sorted(u.get("questions") or [], key=lambda q: q.get("position") or 0)
            for q in u["questions"]:
                a = (q.get("answers") or [{}])[0]
                q["verified"] = bool(a.get("verified"))
                q["confidence"] = a.get("confidence")
                q["has_answer"] = bool(q.get("answers"))
    return subs or []


def fetch_answer(question_id: str) -> dict | None:
    select = ("id,summary,answer,final_answer,followups,confidence,verified,model_used,"
              "diagram_png_watch,diagram_png_phone,variant")
    rows = sb("GET", f"/rest/v1/answers?question_id=eq.{urllib.parse.quote(question_id)}"
                     f"&variant=eq.default&select={urllib.parse.quote(select)}")
    if not rows:
        return None
    a = rows[0]
    a["has_diagram"] = bool(a.get("diagram_png_phone") or a.get("diagram_png_watch"))
    a["diagram_path"] = a.get("diagram_png_phone") or a.get("diagram_png_watch")
    return a


def sign_diagram(path: str) -> str | None:
    try:
        res = sb("POST", f"/storage/v1/object/sign/diagrams/{urllib.parse.quote(path)}",
                 body={"expiresIn": 3600})
        signed = (res or {}).get("signedURL")
        return f"{SB_URL}/storage/v1{signed}" if signed else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _host_ok(self) -> bool:
        return self.headers.get("Host", "") in ALLOWED_HOSTS

    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, b"forbidden host", "text/plain")
        p = urllib.parse.urlparse(self.path)
        try:
            if p.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif p.path == "/api/tree":
                self._json(fetch_tree())
            elif p.path == "/api/answer":
                qid = (urllib.parse.parse_qs(p.query).get("question_id") or [""])[0]
                self._json(fetch_answer(qid) or {})
            elif p.path == "/api/diagram":
                path = (urllib.parse.parse_qs(p.query).get("path") or [""])[0]
                url = sign_diagram(path) if path else None
                if url:
                    self.send_response(302); self.send_header("Location", url); self.end_headers()
                else:
                    self._send(404, b"no diagram", "text/plain")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, b"forbidden host", "text/plain")
        if "application/json" not in self.headers.get("Content-Type", ""):
            return self._json({"error": "json content-type required"}, 415)
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "bad json"}, 400)
        p = urllib.parse.urlparse(self.path)
        try:
            if p.path == "/api/create":
                self._json(insert_row(body["table"], body["row"]))
            elif p.path == "/api/update":
                patch_row(body["table"], body["id"], body["fields"]); self._json({"ok": True})
            elif p.path == "/api/delete":
                delete_tree(body["type"], body["id"]); self._json({"ok": True})
            elif p.path == "/api/verify":
                patch_row("answers", body["id"], {"verified": bool(body.get("verified"))}); self._json({"ok": True})
            elif p.path == "/api/save":
                patch_row("answers", body["id"],
                          {k: body[k] for k in ("summary", "answer", "final_answer") if k in body})
                self._json({"ok": True})
            elif p.path == "/api/upload":
                raw = base64.b64decode(body["data_b64"])
                self._json({"questions": parse_upload(body["filename"], raw)})
            elif p.path == "/api/generate":
                self._json(generate_for_question(body["question_id"], body.get("marks")))
            else:
                self._json({"error": "unknown route"}, 404)
        except urllib.error.HTTPError as e:  # surface Supabase/DeepSeek errors
            self._json({"error": f"{e.code}: {e.read().decode()[:300]}"}, 502)
        except Exception as e:
            self._json({"error": str(e)}, 500)


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>TutorBank Dashboard</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.5 -apple-system,system-ui,sans-serif; background:#0d0d0f; color:#e7e7ea; display:flex; height:100vh; }
  #side { width:360px; border-right:1px solid #26262b; overflow-y:auto; flex:none; display:flex; flex-direction:column; }
  #main { flex:1; overflow-y:auto; padding:20px 26px; }
  .tabs { display:flex; border-bottom:1px solid #26262b; }
  .tab { flex:1; text-align:center; padding:12px; cursor:pointer; color:#9a9aa2; }
  .tab.on { color:#fff; border-bottom:2px solid #2b6cff; }
  .pane { display:none; padding:10px; }
  .pane.on { display:block; }
  .subj { margin-bottom:6px; }
  .subj > .hd { display:flex; align-items:center; gap:6px; padding:7px 8px; background:#17171b; border-radius:8px; cursor:pointer; font-weight:600; }
  .unit > .hd { display:flex; align-items:center; gap:6px; padding:5px 8px 5px 20px; color:#c9c9cf; cursor:pointer; }
  .q { display:flex; align-items:center; gap:6px; padding:4px 8px 4px 34px; font-size:12px; color:#b3b3bb; cursor:pointer; border-radius:6px; }
  .q:hover, .unit>.hd:hover { background:#161619; }
  .q.sel { background:#1d2733; }
  .dot { width:7px; height:7px; border-radius:50%; flex:none; }
  .green { background:#3fbf6b; } .amber { background:#e0a53a; } .grey { background:#4a4a52; }
  .x { margin-left:auto; color:#6a6a72; font-size:12px; padding:0 4px; }
  .x:hover { color:#ff6b6b; }
  button, .btn { font:13px system-ui; padding:7px 12px; border-radius:8px; border:1px solid #34343a; background:#1c1c20; color:#e7e7ea; cursor:pointer; }
  button.primary { background:#2b6cff; border-color:#2b6cff; }
  button.good { background:#1f8f45; border-color:#1f8f45; }
  button:disabled { opacity:.5; cursor:default; }
  .add { font-size:12px; padding:3px 8px; margin:4px 0 8px 20px; }
  h2 { font-size:14px; margin:16px 0 6px; color:#9a9aa2; }
  textarea, input, select { width:100%; background:#141418; color:#e7e7ea; border:1px solid #303036; border-radius:8px; padding:9px; font:13px/1.5 ui-monospace,monospace; }
  textarea { resize:vertical; }
  .qtext { color:#c9c9cf; background:#141418; padding:10px 12px; border-radius:8px; }
  .preview { background:#141418; border:1px solid #26262b; border-radius:8px; padding:12px; margin-top:8px; }
  .preview .sum { font-size:17px; font-weight:600; margin-bottom:8px; }
  .preview pre { background:#0a0a0c; padding:8px 10px; border-radius:6px; overflow-x:auto; font:12px/1.45 ui-monospace,monospace; white-space:pre; }
  img.diagram { max-width:100%; border-radius:8px; background:#fff; margin-top:8px; }
  .muted { color:#7a7a82; font-size:12px; }
  .row { display:flex; gap:8px; align-items:center; margin:6px 0; }
  .prog { height:6px; background:#26262b; border-radius:3px; overflow:hidden; }
  .prog > div { height:100%; background:#2b6cff; width:0; transition:width .3s; }
  table.parsed { width:100%; border-collapse:collapse; font-size:12px; }
  table.parsed td, table.parsed th { border-bottom:1px solid #26262b; padding:5px; text-align:left; vertical-align:top; }
  .actions { display:flex; gap:8px; margin:14px 0; flex-wrap:wrap; }
</style></head><body>
<div id="side">
  <div class="tabs">
    <div class="tab on" data-t="content" onclick="tab('content')">Content</div>
    <div class="tab" data-t="review" onclick="tab('review')">Review</div>
  </div>
  <div id="pane-content" class="pane on">
    <button class="primary" style="width:100%" onclick="newSubject()">+ Subject</button>
    <div id="tree" style="margin-top:10px">Loading…</div>
  </div>
  <div id="pane-review" class="pane">
    <div class="muted" id="revcount" style="padding:8px"></div>
    <div id="revrows"></div>
  </div>
</div>
<div id="main"><p class="muted">Pick a question, or upload an assignment (choose a subject → Upload).</p></div>
<script>
let tree = [], cur = null, curQ = null;
function esc(s){ return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
async function api(path, body){ const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const j=await r.json(); if(j.error) throw new Error(j.error); return j; }
async function get(path){ const r=await fetch(path); return r.json(); }
function tab(t){ document.querySelectorAll('.tab').forEach(x=>x.classList.toggle('on',x.dataset.t===t)); document.querySelectorAll('.pane').forEach(x=>x.classList.remove('on')); document.getElementById('pane-'+t).classList.add('on'); if(t==='review') loadReview(); }

async function loadTree(){ tree = await get('/api/tree'); renderTree(); }
function dotClass(q){ if(!q.has_answer) return 'grey'; return q.verified?'green':'amber'; }
function renderTree(){
  const el = document.getElementById('tree'); el.innerHTML='';
  tree.forEach(s=>{
    const sd=document.createElement('div'); sd.className='subj';
    sd.innerHTML=`<div class="hd">${esc(s.code)} · ${esc(s.name)}<span class="x" onclick="del(event,'subject','${s.id}','${esc(s.code)}')">✕</span></div>`;
    const body=document.createElement('div');
    (s.units||[]).forEach(u=>{
      const ud=document.createElement('div'); ud.className='unit';
      ud.innerHTML=`<div class="hd">${esc(u.name)}<span class="x" onclick="del(event,'unit','${u.id}','${esc(u.name)}')">✕</span></div>`;
      (u.questions||[]).forEach(q=>{
        const qd=document.createElement('div'); qd.className='q'+(curQ===q.id?' sel':''); qd.dataset.qid=q.id;
        qd.innerHTML=`<span class="dot ${dotClass(q)}"></span>${esc(q.text.slice(0,46))}<span class="x" onclick="del(event,'question','${q.id}','question')">✕</span>`;
        qd.onclick=(e)=>{ if(e.target.classList.contains('x'))return; curQ=q.id; renderTree(); openQuestion(s,u,q); };
        ud.appendChild(qd);
      });
      const add=document.createElement('button'); add.className='btn add'; add.textContent='+ question'; add.onclick=()=>newQuestion(s,u); ud.appendChild(add);
      body.appendChild(ud);
    });
    const bar=document.createElement('div'); bar.style.margin='6px 0 10px 20px'; bar.className='row';
    bar.innerHTML=`<button class="btn" onclick="newUnit('${s.id}')">+ Unit</button><button class="btn" onclick="uploadFor(${JSON.stringify(s).replace(/"/g,'&quot;')})">⬆ Upload assignment</button>`;
    body.appendChild(bar);
    sd.appendChild(body); el.appendChild(sd);
  });
}

async function del(e,type,id,label){ e.stopPropagation(); if(!confirm('Delete '+label+' and everything under it?'))return; await api('/api/delete',{type,id}); if(curQ===id)curQ=null; loadTree(); }
async function newSubject(){ const code=prompt('Subject code (e.g. PHY):'); if(!code)return; const name=prompt('Subject name:')||code; await api('/api/create',{table:'subjects',row:{code,name}}); loadTree(); }
async function newUnit(sid){ const name=prompt('Unit name (e.g. Unit 1 — Kinematics):'); if(!name)return; const s=tree.find(x=>x.id===sid); const pos=(s.units||[]).length+1; await api('/api/create',{table:'units',row:{subject_id:sid,name,position:pos}}); loadTree(); }
async function newQuestion(s,u){ const text=prompt('Question text:'); if(!text)return; const qtype=prompt('qtype (concept/solve/proof/diagram/predict_output/program):','concept')||'concept'; const pos=(u.questions||[]).length+1; const q=await api('/api/create',{table:'questions',row:{unit_id:u.id,text,qtype,position:pos}}); await loadTree(); if(confirm('Generate an answer now with DeepSeek?')){ await genOne(q.id,null,'question'); loadTree(); } }

async function openQuestion(s,u,q){
  const a = await get('/api/answer?question_id='+q.id);
  const hasA = a && a.id;
  document.getElementById('main').innerHTML = `
    <div class="muted">${esc(s.code)} · ${esc(u.name)} · ${esc(q.qtype)}</div>
    <h2>Question</h2><div class="qtext">${esc(q.text)}</div>
    <div class="actions">
      <button class="primary" onclick="genOne('${q.id}',null,'main')">${hasA?'Regenerate':'Generate'} answer (DeepSeek)</button>
    </div>
    ${hasA ? answerEditor(a) : '<p class="muted">No answer yet — Generate to create one.</p>'}`;
}
function answerEditor(a){
  const dg = a.has_diagram ? `<img class="diagram" src="/api/diagram?path=${encodeURIComponent(a.diagram_path)}">` : '';
  return `<h2>Summary</h2><textarea id="ed_s" rows="2">
${esc(a.summary)}</textarea>
    <h2>Answer</h2><textarea id="ed_a" rows="14">
${esc(a.answer)}</textarea>
    <h2>Preview</h2><div class="preview"><div class="sum" id="pv_s">${esc(a.summary)}</div>${dg}<div id="pv_a">${fenced(a.answer)}</div></div>
    <div class="actions">
      <button class="primary" onclick="saveA('${a.id}')">Save edits</button>
      <button class="${a.verified?'':'good'}" onclick="verifyA('${a.id}',${!a.verified})">${a.verified?'Mark unverified':'✓ Mark verified'}</button>
      <span class="muted" id="st"></span></div>`;
}
function fenced(s){ const p=(s||'').split('```'); let o=''; p.forEach((x,i)=>{ if(i%2){o+='<pre>'+esc(x.replace(/^\w*\n/,''))+'</pre>';} else o+='<div>'+esc(x).replace(/\n/g,'<br>')+'</div>'; }); return o; }
function bind(){ const s=document.getElementById('ed_s'), a=document.getElementById('ed_a'); if(!s)return; const up=()=>{document.getElementById('pv_s').textContent=s.value; document.getElementById('pv_a').innerHTML=fenced(a.value);}; s.oninput=up; a.oninput=up; }
async function saveA(id){ await api('/api/save',{id,summary:val('ed_s'),answer:val('ed_a')}); note('saved'); loadTree(); }
async function verifyA(id,v){ await api('/api/verify',{id,verified:v}); note(v?'verified':'unverified'); loadTree(); const q=curQ; if(q){const found=findQ(q); if(found) openQuestion(found.s,found.u,found.q);} }
function val(id){ return document.getElementById(id).value; }
function note(t){ const s=document.getElementById('st'); if(s){s.textContent=t; setTimeout(()=>s.textContent='',1800);} }
function findQ(qid){ for(const s of tree) for(const u of s.units||[]) for(const q of u.questions||[]) if(q.id===qid) return {s,u,q}; return null; }

async function genOne(qid, marks, ctx){ try{ note('generating…'); await api('/api/generate',{question_id:qid, marks}); if(ctx==='main'){ const f=findQ(qid)||await refindAfterInsert(qid); } await loadTree(); const f=findQ(qid); if(f) openQuestion(f.s,f.u,f.q); }catch(e){ alert('Generate failed: '+e.message); } }
async function refindAfterInsert(qid){ await loadTree(); return findQ(qid); }

// ---- upload flow ----
function uploadFor(subject){
  const inp=document.createElement('input'); inp.type='file'; inp.accept='.docx,.pdf';
  inp.onchange=async()=>{ const f=inp.files[0]; if(!f)return;
    const b64=await fileB64(f);
    document.getElementById('main').innerHTML='<p class="muted">Parsing '+esc(f.name)+'…</p>';
    let res; try{ res=await api('/api/upload',{filename:f.name,data_b64:b64}); }catch(e){ document.getElementById('main').innerHTML='<p style="color:#ff6b6b">Parse failed: '+esc(e.message)+'</p>'; return; }
    showParsed(subject, f.name, res.questions);
  };
  inp.click();
}
function fileB64(f){ return new Promise(res=>{ const r=new FileReader(); r.onload=()=>res(r.result.split(',')[1]); r.readAsDataURL(f); }); }
function showParsed(subject, fname, qs){
  const units=(subject.units||[]).map(u=>`<option value="${u.id}">${esc(u.name)}</option>`).join('');
  document.getElementById('main').innerHTML=`
    <h2>Parsed ${qs.length} questions from ${esc(fname)}</h2>
    <div class="row"><label>Into unit:</label>
      <select id="up_unit">${units}<option value="__new">➕ new unit…</option></select></div>
    <div class="row"><label>Assignment title:</label><input id="up_asg" value="${esc(fname.replace(/\.[^.]+$/,''))}"></div>
    <table class="parsed"><thead><tr><th>#</th><th>qtype</th><th>marks</th><th>question</th></tr></thead><tbody>
    ${qs.map((q,i)=>`<tr><td>${i+1}</td><td><select data-i="${i}" class="qt">
      ${['concept','solve','proof','diagram','predict_output','program'].map(t=>`<option ${t===q.qtype?'selected':''}>${t}</option>`).join('')}
      </select></td><td>${q.marks||''}</td><td>${esc(q.text)}</td></tr>`).join('')}
    </tbody></table>
    <div class="actions">
      <button class="primary" id="go" onclick='ingest(${JSON.stringify({subject_id:subject.id, subject_code:subject.code})}, ${JSON.stringify(qs)})'>Generate &amp; insert all (${qs.length})</button>
    </div>
    <div class="prog" style="margin-top:10px"><div id="pbar"></div></div>
    <div class="muted" id="pmsg" style="margin-top:6px"></div>`;
}
async function ingest(meta, qs){
  document.getElementById('go').disabled=true;
  // qtype overrides from the table
  document.querySelectorAll('.qt').forEach(sel=>{ qs[+sel.dataset.i].qtype = sel.value; });
  let unitId=document.getElementById('up_unit').value;
  if(unitId==='__new'){ const nm=prompt('New unit name:'); if(!nm){document.getElementById('go').disabled=false;return;} const u=await api('/api/create',{table:'units',row:{subject_id:meta.subject_id,name:nm,position:999}}); unitId=u.id; }
  const asg=await api('/api/create',{table:'assignments',row:{subject_id:meta.subject_id,title:document.getElementById('up_asg').value,source_file:qs[0]&&qs[0].source_file}});
  const bar=document.getElementById('pbar'), msg=document.getElementById('pmsg');
  for(let i=0;i<qs.length;i++){
    msg.textContent=`Generating ${i+1}/${qs.length}: ${qs[i].text.slice(0,50)}…`;
    try{
      const q=await api('/api/create',{table:'questions',row:{unit_id:unitId,assignment_id:asg.id,text:qs[i].text,qtype:qs[i].qtype,position:i+1}});
      await api('/api/generate',{question_id:q.id, marks:qs[i].marks});
    }catch(e){ msg.textContent=`Q${i+1} failed: ${e.message}`; }
    bar.style.width=Math.round((i+1)/qs.length*100)+'%';
  }
  msg.textContent=`Done — ${qs.length} questions generated. Review them in the Review tab.`;
  loadTree();
}

// ---- review queue ----
async function loadReview(){
  const items = await get('/api/tree');
  const flat=[];
  items.forEach(s=>(s.units||[]).forEach(u=>(u.questions||[]).forEach(q=>{ if(q.has_answer) flat.push({s,u,q}); })));
  flat.sort((a,b)=>(a.q.verified-b.q.verified)||((a.q.confidence??1)-(b.q.confidence??1)));
  const pend=flat.filter(x=>!x.q.verified).length;
  document.getElementById('revcount').textContent=`${pend} to review · ${flat.length} with answers`;
  const el=document.getElementById('revrows'); el.innerHTML='';
  flat.forEach(x=>{ const d=document.createElement('div'); d.className='q'; d.style.paddingLeft='10px';
    d.innerHTML=`<span class="dot ${x.q.verified?'green':'amber'}"></span>${esc(x.s.code)} · ${esc(x.q.text.slice(0,40))}`;
    d.onclick=()=>{ curQ=x.q.id; openQuestion(x.s,x.u,x.q); tab('content'); document.querySelector('.tab[data-t=content]').classList.add('on'); };
    el.appendChild(d);
  });
}
const _oldOpen=openQuestion;
openQuestion=async function(s,u,q){ await _oldOpen(s,u,q); bind(); };
loadTree();
</script></body></html>"""


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"TutorBank dashboard → {url}  (Ctrl-C to stop)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
