#!/usr/bin/env python3
"""TutorBank Mac verification & content tool (CLAUDE.md §7, §9 M4).

A local, localhost-only web app to review generated answers: queues
unverified / low-confidence first, renders each like the watch (code blocks
monospaced, diagram shown), and lets you edit the summary/answer and flip
`verified`. Writes straight to Supabase via the service-role key from ../.env.

Run:
    cd ingestion && python3 review.py     # opens http://127.0.0.1:8765

No external dependencies (stdlib only). Do NOT expose beyond localhost — it
holds the service key.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8765


def load_env() -> dict:
    env: dict[str, str] = {}
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        raise SystemExit("missing ../.env — fill in SUPABASE_URL and SUPABASE_SERVICE_KEY")
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


def sb(method: str, path: str, body: dict | None = None, extra_headers: dict | None = None):
    url = f"{SB_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "apikey": SVC,
        "Authorization": f"Bearer {SVC}",
        "Content-Type": "application/json",
        "User-Agent": "tutorbank-review/1",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        raw = resp.read()
        return json.loads(raw) if raw else None


def fetch_queue() -> list[dict]:
    """All default-variant answers with question/unit/subject context,
    ordered: unverified first, then lowest confidence, then subject/unit/position."""
    select = (
        "id,summary,answer,final_answer,followups,confidence,verified,model_used,"
        "diagram_png_watch,diagram_png_phone,"
        "question:questions!inner(text,qtype,position,"
        "unit:units!inner(name,position,subject:subjects!inner(code,name)))"
    )
    rows = sb("GET", f"/rest/v1/answers?select={urllib.parse.quote(select)}&variant=eq.default")
    items = []
    for r in rows or []:
        q = r.get("question") or {}
        u = q.get("unit") or {}
        s = u.get("subject") or {}
        items.append({
            "id": r["id"],
            "summary": r.get("summary") or "",
            "answer": r.get("answer") or "",
            "final_answer": r.get("final_answer") or "",
            "followups": r.get("followups") or [],
            "confidence": r.get("confidence"),
            "verified": bool(r.get("verified")),
            "model_used": r.get("model_used") or "",
            "has_diagram": bool(r.get("diagram_png_phone") or r.get("diagram_png_watch")),
            "diagram_path": r.get("diagram_png_phone") or r.get("diagram_png_watch"),
            "qtype": q.get("qtype") or "",
            "qtext": q.get("text") or "",
            "position": q.get("position") or 0,
            "unit": u.get("name") or "",
            "unit_pos": u.get("position") or 0,
            "subject": s.get("code") or "",
            "subject_name": s.get("name") or "",
        })
    items.sort(key=lambda x: (
        x["verified"],
        x["confidence"] if x["confidence"] is not None else 1.0,
        x["subject"], x["unit_pos"], x["position"],
    ))
    return items


def sign_diagram(path: str) -> str | None:
    try:
        res = sb("POST", f"/storage/v1/object/sign/diagrams/{urllib.parse.quote(path)}",
                 body={"expiresIn": 3600})
        signed = (res or {}).get("signedURL")
        return f"{SB_URL}/storage/v1{signed}" if signed else None
    except Exception:
        return None


def patch_answer(answer_id: str, fields: dict) -> None:
    sb("PATCH", f"/rest/v1/answers?id=eq.{urllib.parse.quote(answer_id)}",
       body=fields, extra_headers={"Prefer": "return=minimal"})


# Only these Host values are served — defeats DNS-rebinding, where a page on an
# attacker domain rebound to 127.0.0.1 would otherwise reach this tool same-origin.
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
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
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif parsed.path == "/api/queue":
            try:
                self._json(fetch_queue())
            except Exception as e:
                self._json({"error": str(e)}, 500)
        elif parsed.path == "/api/diagram":
            qs = urllib.parse.parse_qs(parsed.query)
            path = (qs.get("path") or [""])[0]
            url = sign_diagram(path) if path else None
            if url:
                self.send_response(302)
                self.send_header("Location", url)
                self.end_headers()
            else:
                self._send(404, b"no diagram", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, b"forbidden host", "text/plain")
        # Require application/json: blocks cross-origin CORS "simple request" writes
        # (text/plain would skip the preflight that our missing CORS headers rely on).
        if "application/json" not in self.headers.get("Content-Type", ""):
            return self._json({"error": "json content-type required"}, 415)
        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return self._json({"error": "bad json"}, 400)
        parsed = urllib.parse.urlparse(self.path)
        answer_id = payload.get("id")
        if not answer_id:
            return self._json({"error": "id required"}, 400)
        try:
            if parsed.path == "/api/verify":
                patch_answer(answer_id, {"verified": bool(payload.get("verified"))})
            elif parsed.path == "/api/save":
                fields = {k: payload.get(k) for k in ("summary", "answer", "final_answer")
                          if k in payload}
                if not fields:
                    return self._json({"error": "nothing to save"}, 400)
                patch_answer(answer_id, fields)
            else:
                return self._json({"error": "unknown route"}, 404)
            self._json({"ok": True})
        except Exception as e:
            self._json({"error": str(e)}, 500)


PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<title>TutorBank Review</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; font:14px/1.5 -apple-system,system-ui,sans-serif; background:#0d0d0f; color:#e7e7ea; display:flex; height:100vh; }
  #list { width:340px; border-right:1px solid #26262b; overflow-y:auto; flex:none; }
  #detail { flex:1; overflow-y:auto; padding:20px 26px; }
  .hdr { padding:12px 14px; border-bottom:1px solid #26262b; position:sticky; top:0; background:#0d0d0f; font-weight:600; }
  .row { padding:10px 14px; border-bottom:1px solid #1b1b1f; cursor:pointer; }
  .row:hover { background:#161619; }
  .row.sel { background:#1d2733; }
  .row .q { color:#c9c9cf; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
  .badges { margin-top:4px; display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
  .tag { font-size:11px; padding:1px 6px; border-radius:4px; }
  .subj { background:#2a2f3a; color:#9fc1ff; }
  .conf { background:#332a2a; color:#ffb4a3; }
  .ok { background:#1f3524; color:#8ff0a4; }
  .pend { background:#3a3320; color:#ffd78a; }
  textarea { width:100%; background:#141418; color:#e7e7ea; border:1px solid #303036; border-radius:8px; padding:10px; font:13px/1.5 ui-monospace,monospace; resize:vertical; }
  h2 { font-size:15px; margin:18px 0 6px; color:#9a9aa2; }
  .qtext { color:#c9c9cf; background:#141418; padding:10px 12px; border-radius:8px; }
  .preview { background:#141418; border:1px solid #26262b; border-radius:8px; padding:12px; }
  .preview .sum { font-size:18px; font-weight:600; margin-bottom:8px; }
  .preview pre { background:#0a0a0c; padding:8px 10px; border-radius:6px; overflow-x:auto; font:12px/1.45 ui-monospace,monospace; }
  .actions { position:sticky; bottom:0; background:#0d0d0f; padding:14px 0; display:flex; gap:10px; }
  button { font:14px system-ui; padding:9px 16px; border-radius:8px; border:1px solid #34343a; background:#1c1c20; color:#e7e7ea; cursor:pointer; }
  button.primary { background:#2b6cff; border-color:#2b6cff; }
  button.good { background:#1f8f45; border-color:#1f8f45; }
  button:disabled { opacity:.5; cursor:default; }
  img.diagram { max-width:100%; border-radius:8px; background:#fff; margin-top:8px; }
  .muted { color:#7a7a82; font-size:12px; }
</style></head><body>
<div id="list"><div class="hdr" id="counts">Loading…</div><div id="rows"></div></div>
<div id="detail"><p class="muted">Select an answer on the left. Unverified &amp; low-confidence are sorted first.</p></div>
<script>
let items = [], cur = null;
async function load() {
  items = await (await fetch('/api/queue')).json();
  render();
}
function render() {
  const pend = items.filter(i=>!i.verified).length;
  document.getElementById('counts').textContent = `${pend} to review · ${items.length} total`;
  const el = document.getElementById('rows'); el.innerHTML = '';
  items.forEach((it, idx) => {
    const d = document.createElement('div');
    d.className = 'row' + (cur===idx?' sel':'');
    const conf = it.confidence==null ? '—' : it.confidence.toFixed(2);
    d.innerHTML = `<div class="q">${esc(it.qtext)}</div>
      <div class="badges">
        <span class="tag subj">${it.subject}·U${it.unit_pos}Q${it.position}</span>
        <span class="tag ${it.confidence!=null&&it.confidence<0.9?'conf':'muted'}">conf ${conf}</span>
        <span class="tag ${it.verified?'ok':'pend'}">${it.verified?'verified':'pending'}</span>
        ${it.has_diagram?'<span class="tag muted">◈ diagram</span>':''}
      </div>`;
    d.onclick = () => { cur = idx; render(); detail(); };
    el.appendChild(d);
  });
}
function esc(s){ return (s||'').replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }
function fenced(s){
  const parts = (s||'').split('```'); let out='';
  parts.forEach((p,i)=>{ if(i%2){ let t=p.replace(/^\w*\n/,''); out+='<pre>'+esc(t)+'</pre>'; } else out+='<div>'+esc(p).replace(/\n/g,'<br>')+'</div>'; });
  return out;
}
function detail() {
  const it = items[cur]; if(!it) return;
  const dg = it.has_diagram ? `<img class="diagram" src="/api/diagram?path=${encodeURIComponent(it.diagram_path)}">` : '';
  document.getElementById('detail').innerHTML = `
    <div class="muted">${it.subject_name} — ${esc(it.unit)} · ${it.qtype} · ${it.model_used}</div>
    <h2>Question</h2><div class="qtext">${esc(it.qtext)}</div>
    <h2>Summary (glance line)</h2><textarea id="ed_summary" rows="2">
${esc(it.summary)}</textarea>
    <h2>Answer (full working)</h2><textarea id="ed_answer" rows="16">
${esc(it.answer)}</textarea>
    <h2>Preview</h2>
    <div class="preview"><div class="sum" id="pv_sum">${esc(it.summary)}</div>${dg}<div id="pv_ans">${fenced(it.answer)}</div></div>
    <div class="actions">
      <button class="primary" onclick="save()">Save edits</button>
      <button class="${it.verified?'':'good'}" onclick="toggleVerify()">${it.verified? 'Mark unverified':'✓ Mark verified'}</button>
      <span class="muted" id="status"></span>
    </div>`;
  const upd = () => { document.getElementById('pv_sum').textContent = sVal('ed_summary');
                      document.getElementById('pv_ans').innerHTML = fenced(sVal('ed_answer')); };
  document.getElementById('ed_summary').oninput = upd;
  document.getElementById('ed_answer').oninput = upd;
}
function sVal(id){ return document.getElementById(id).value; }
async function save() {
  const it = items[cur];
  it.summary = sVal('ed_summary'); it.answer = sVal('ed_answer');
  await post('/api/save', {id: it.id, summary: it.summary, answer: it.answer});
  status('saved');
}
async function toggleVerify() {
  const it = items[cur]; it.verified = !it.verified;
  await post('/api/verify', {id: it.id, verified: it.verified});
  render(); detail();
}
async function post(url, body){
  const r = await (await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  if(r.error){ status('error: '+r.error); throw r.error; }
  return r;
}
function status(t){ const s=document.getElementById('status'); if(s){ s.textContent=t; setTimeout(()=>s.textContent='',2000);} }
load();
</script></body></html>"""


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"TutorBank review tool → {url}  (Ctrl-C to stop)")
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
