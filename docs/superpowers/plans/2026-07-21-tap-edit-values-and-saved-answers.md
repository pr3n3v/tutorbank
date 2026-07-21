# Tap-to-Edit Values & Saved Answers — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user re-solve a maths question with different values via an on-watch chip
editor (non-destructive), and auto-save every DeepSeek answer per subject, browsable on the
watch and deletable from the Mac dashboard.

**Architecture:** Runtime tokenizer splits a question into fixed/editable segments; a
hub-and-spoke SwiftUI editor edits one value per screen and reconstructs a modified question
string that is sent to the existing `/ask` Edge Function (solve mode). `/ask` gains an
optional `subject_id`/`source` and best-effort-inserts every result into a new `saved_answers`
table. A new `/saved` Edge Function lists them; the watch shows them read-only; the dashboard
deletes them. The canonical `questions`/`answers` rows are never mutated.

**Tech Stack:** watchOS SwiftUI (Xcode 26.6, watchOS 26.5, XcodeGen), Deno/TypeScript Supabase
Edge Functions (`@supabase/supabase-js@2`), Postgres (Supabase), Python 3 stdlib dashboard
(`ingestion/dashboard.py`), sympy/poppler already installed.

## Global Constraints

- Watch has NO LaTeX engine. Unicode math only. **Digit** sub/superscripts may be Unicode
  (`x²`, `x₁`, `A⁻¹`); **letter** indices/exponents must be ASCII (`a_ij`, `A^T`, `a^n`,
  `a_(n+1)`) — the watchOS font lacks glyphs like subscript-j. Enforced in
  `ingestion/dashboard.py` `_script` and `_shared/mathtext.ts` `script()`.
- Edge Functions authenticate with header `X-App-Secret` via `_shared/auth.ts`
  `requireAppSecret`; service-role DB access via `Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")`
  and `Deno.env.get("SUPABASE_URL")`.
- Deploy Edge Functions with: `supabase functions deploy <fn> --workdir /Users/pr3n3v/watch/backend --project-ref $SUPABASE_PROJECT_REF` (token + ref in `/Users/pr3n3v/watch/.env`; `SUPABASE_PROJECT_REF=omhqetywxetxazffxxov`). Docker not required (uploads via API).
- Dashboard writable-table allow-list lives in `ingestion/dashboard.py` `WRITABLE`; cascade
  deletes go through `delete_tree` using `sb_sql` (management API, `User-Agent: curl/8`).
- The physical watch is pending re-sign; **all watch verification is on the SE 3 44mm sim**
  (`BFF2EE35-2447-4F35-A9A5-957C4D0D4277`, watchOS 26.5). Sim build:
  `xcodebuild -project app/TutorBank.xcodeproj -scheme TutorBankWatch -destination 'platform=watchOS Simulator,id=BFF2EE35-2447-4F35-A9A5-957C4D0D4277' -derivedDataPath <dd> CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build`.
- Bundle id: `com.pr3n3v.notesbank688c9257.watchkitapp`. EM2 subject id
  `4c389c9a-c837-43da-a073-d418971dce7f`.
- Never mutate `questions`/`answers` rows from the tap-edit flow. Frequent commits; repo-local
  git identity is already set.

---

## File Structure

**Backend / DB**
- Create `backend/supabase/migrations/0003_saved_answers.sql` — `saved_answers` table + index + RLS.
- Modify `backend/supabase/functions/ask/index.ts` — accept `subject_id`/`source`; best-effort save.
- Create `backend/supabase/functions/saved/index.ts` — `POST /saved {subject_id}` list.

**Dashboard**
- Modify `ingestion/dashboard.py` — `fetch_saved`, `/api/saved` route, `delete_tree` kind
  `saved_answer`, `SAVED`-tab HTML/JS in the embedded SPA.

**Watch — tap-to-edit**
- Create `app/TutorBankWatch/Models/QuestionTokenizer.swift` — pure tokenizer + reconstruct.
- Create `app/TutorBankWatch/Views/FlowLayout.swift` — wrapping `Layout`.
- Create `app/TutorBankWatch/Views/ValueEditKeypadView.swift` — single-cell editor.
- Create `app/TutorBankWatch/Views/ValueEditHubView.swift` — chip hub + Solve (replaces `ValueSwapView`).
- Delete `app/TutorBankWatch/Views/ValueSwapView.swift`.
- Modify `app/TutorBankWatch/Views/AnswerView.swift` — "Change the numbers" entry.
- Modify `app/TutorBankWatch/Services/AskService.swift` — `subjectId`/`source` params + `fetchSaved`.
- Modify `app/TutorBankWatch/Views/LiveAnswerView.swift` — pass `subjectId`/`source` through.

**Watch — saved answers**
- Create `app/TutorBankWatch/Views/SavedAnswersListView.swift` — list + detail.
- Modify `app/TutorBankWatch/Views/TutorRootView.swift` — "Saved Answers" row per subject, "General" row on the Subjects list.

**Tests**
- Create a **new watchOS unit-test target** `TutorBankWatchTests` (the existing
  `TutorBankWatchUITests` is a black-box UI target and cannot `@testable import` app code).
- Create `app/TutorBankWatchTests/QuestionTokenizerTests.swift` — tokenizer unit tests.

Add the new Swift files to `app/project.yml` sources if it enumerates files explicitly; if it
globs the folders, only the new **target** needs adding (Task 6). Regenerate with
`cd app && xcodegen generate` after any `project.yml` change.

---

## Phase 1 — Backend & Data

### Task 1: `saved_answers` table migration

**Files:**
- Create: `backend/supabase/migrations/0003_saved_answers.sql`
- Test: manual `psql`/PostgREST check (no unit framework for SQL here)

**Interfaces:**
- Produces: table `saved_answers(id uuid, subject_id uuid null, question_text text, summary text, answer text, model text, source text, created_at timestamptz)`.

- [ ] **Step 1: Write the migration**

```sql
-- 0003_saved_answers.sql — persisted DeepSeek /ask results (Ask-about-this, tap-edit, chat).
-- subject_id NULL = the "General" bucket (free-chat). Canonical questions/answers untouched.
create table if not exists saved_answers (
  id            uuid primary key default gen_random_uuid(),
  subject_id    uuid references subjects(id) on delete cascade,
  question_text text not null,
  summary       text not null,
  answer        text,
  model         text,
  source        text not null default 'ask'
                check (source in ('ask', 'tap_edit', 'chat')),
  created_at    timestamptz not null default now()
);

create index if not exists idx_saved_answers_subject
  on saved_answers (subject_id, created_at desc);

-- Deny-by-default RLS like every other table (only the service role touches it).
alter table saved_answers enable row level security;
```

- [ ] **Step 2: Apply the migration**

Run:
```bash
cd /Users/pr3n3v/watch && set -a && source .env && set +a
supabase db push --workdir /Users/pr3n3v/watch/backend --project-ref "$SUPABASE_PROJECT_REF"
```
Expected: output lists `0003_saved_answers.sql` applied. If `db push` is unavailable, apply
via the management API `execute_sql` with the file contents (same path used for deletes).

- [ ] **Step 3: Verify the table + insert/read round-trips**

Run:
```bash
cd /Users/pr3n3v/watch && set -a && source .env && set +a
curl -sS -X POST "$SUPABASE_URL/rest/v1/saved_answers" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" \
  -H "Content-Type: application/json" -H "Prefer: return=representation" \
  -d '{"subject_id":null,"question_text":"probe","summary":"probe","source":"chat"}'
```
Expected: a JSON row with an `id` and `created_at`. Then delete it:
```bash
curl -sS -X DELETE "$SUPABASE_URL/rest/v1/saved_answers?question_text=eq.probe" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY"
```
Expected: HTTP 204.

- [ ] **Step 4: Commit**

```bash
git add backend/supabase/migrations/0003_saved_answers.sql
git commit -m "feat(db): saved_answers table for persisted /ask results"
```

---

### Task 2: `/ask` accepts `subject_id`/`source` and best-effort-saves

**Files:**
- Modify: `backend/supabase/functions/ask/index.ts`

**Interfaces:**
- Consumes: `saved_answers` (Task 1); `Deno.env` `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
- Produces: `/ask` request now also reads `body.subject_id` (string|null) and `body.source`
  (`'ask'|'tap_edit'|'chat'`, default `'ask'`); response shape unchanged
  (`{summary, answer, model, mode}`). Side effect: one `saved_answers` insert per success.

- [ ] **Step 1: Add a save helper (top of file, after imports)**

```ts
import { createClient } from "jsr:@supabase/supabase-js@2";

// Persist a finished answer. Best-effort: never throws into the request path — a save
// failure must not fail the answer the user is waiting on.
async function saveAnswer(row: {
  subject_id: string | null;
  question_text: string;
  summary: string;
  answer: string;
  model: string;
  source: "ask" | "tap_edit" | "chat";
}): Promise<void> {
  try {
    const url = Deno.env.get("SUPABASE_URL");
    const key = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!url || !key) return;
    const supabase = createClient(url, key, { auth: { persistSession: false } });
    const { error } = await supabase.from("saved_answers").insert(row);
    if (error) console.error("saved_answers insert failed:", error.message);
  } catch (e) {
    console.error("saved_answers insert threw:", e instanceof Error ? e.message : String(e));
  }
}

const VALID_SOURCES = new Set(["ask", "tap_edit", "chat"]);
```

- [ ] **Step 2: Read the new fields where the body is parsed**

Find the body parse block (currently `let body: { prompt?: unknown; mode?: unknown; context?: unknown };`)
and extend the type + reads:

```ts
  let body: { prompt?: unknown; mode?: unknown; context?: unknown; subject_id?: unknown; source?: unknown };
  // ... existing try/catch json parse ...
  const subjectId = typeof body.subject_id === "string" && body.subject_id.trim() ? body.subject_id.trim() : null;
  const source = (typeof body.source === "string" && VALID_SOURCES.has(body.source)) ? body.source as "ask" | "tap_edit" | "chat" : "ask";
```

- [ ] **Step 3: Save just before returning the answer**

Immediately before the final `return json({ summary, answer, model, mode });`, add:

```ts
  // Best-effort persistence — fire and await so we log failures, but wrapped so it can't throw.
  await saveAnswer({ subject_id: subjectId, question_text: prompt, summary, answer, model, source });
```

- [ ] **Step 4: Deploy and smoke-test the save**

Run:
```bash
cd /Users/pr3n3v/watch && set -a && source .env && set +a
supabase functions deploy ask --workdir /Users/pr3n3v/watch/backend --project-ref "$SUPABASE_PROJECT_REF"
curl -sS -X POST "$SUPABASE_URL/functions/v1/ask" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" -H "X-App-Secret: $APP_SHARED_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is 2+2?","mode":"chat","subject_id":null,"source":"chat"}' | python3 -m json.tool
```
Expected: a `{summary, answer, model, mode}` JSON. Then confirm a row landed:
```bash
curl -sS "$SUPABASE_URL/rest/v1/saved_answers?question_text=eq.What%20is%202%2B2%3F&select=source,summary" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY"
```
Expected: one row with `"source":"chat"`. Delete it afterward (DELETE like Task 1 Step 3).

- [ ] **Step 5: Verify a save failure does not break the answer**

Reason: the `saveAnswer` catch guarantees this. Confirm by code inspection that `saveAnswer`
has no `throw` reachable from the request path (all paths caught). No separate command.

- [ ] **Step 6: Commit**

```bash
git add backend/supabase/functions/ask/index.ts
git commit -m "feat(ask): best-effort save every result to saved_answers"
```

---

### Task 3: `/saved` list Edge Function

**Files:**
- Create: `backend/supabase/functions/saved/index.ts`

**Interfaces:**
- Consumes: `_shared/auth.ts` `{ json, requireAppSecret }`; `saved_answers` table.
- Produces: `POST /saved { subject_id: string | "general" }` →
  `[{ id, question_text, summary, answer, model, source, created_at }]` newest-first.

- [ ] **Step 1: Write the function**

```ts
// /saved — list persisted DeepSeek answers for one subject (or "general" = subject_id NULL).
// POST { subject_id: uuid | "general" }. Auth via X-App-Secret.
import { createClient } from "jsr:@supabase/supabase-js@2";
import { json, requireAppSecret } from "../_shared/auth.ts";

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405);
  const denied = await requireAppSecret(req);
  if (denied) return denied;

  let body: { subject_id?: unknown };
  try { body = await req.json(); } catch { return json({ error: "invalid JSON body" }, 400); }
  const raw = typeof body.subject_id === "string" ? body.subject_id.trim() : "";
  if (!raw) return json({ error: "subject_id required" }, 400);

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );

  let q = supabase
    .from("saved_answers")
    .select("id, question_text, summary, answer, model, source, created_at")
    .order("created_at", { ascending: false })
    .limit(200);
  q = raw === "general" ? q.is("subject_id", null) : q.eq("subject_id", raw);

  const { data, error } = await q;
  if (error) return json({ error: "query failed" }, 500);
  return json({ saved: data ?? [] });
});
```

- [ ] **Step 2: Deploy**

Run:
```bash
cd /Users/pr3n3v/watch && set -a && source .env && set +a
supabase functions deploy saved --workdir /Users/pr3n3v/watch/backend --project-ref "$SUPABASE_PROJECT_REF"
```
Expected: `Deployed Functions.` with `"functions":["saved"]`.

- [ ] **Step 3: Smoke-test**

Run (insert a probe row first via Task 1 Step 3 with `source:'chat'`, then):
```bash
curl -sS -X POST "$SUPABASE_URL/functions/v1/saved" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY" -H "X-App-Secret: $APP_SHARED_SECRET" \
  -H "Content-Type: application/json" -d '{"subject_id":"general"}' | python3 -m json.tool
```
Expected: `{"saved":[ ... the probe row ... ]}`. Delete the probe afterward.

- [ ] **Step 4: Commit**

```bash
git add backend/supabase/functions/saved/index.ts
git commit -m "feat(saved): /saved list endpoint for saved answers"
```

---

## Phase 2 — Dashboard (Mac management)

### Task 4: `fetch_saved`, `/api/saved`, delete kind `saved_answer`

**Files:**
- Modify: `ingestion/dashboard.py`

**Interfaces:**
- Consumes: `sb` (PostgREST helper), `sb_sql` (management API), `delete_tree`.
- Produces: `fetch_saved() -> list[dict]` (each `{id, subject, subject_id, question_text, summary, source, created_at}`); route `POST /api/saved` → `{"saved": [...]}`; `delete_tree("saved_answer", id)`.

- [ ] **Step 1: Add `fetch_saved()` near the other `fetch_*` helpers**

```python
def fetch_saved() -> list:
    """All saved answers with their subject name (None -> 'General'), newest first."""
    select = "id,subject_id,question_text,summary,source,created_at,subject:subjects(name)"
    rows = sb("GET", f"/rest/v1/saved_answers?select={urllib.parse.quote(select)}"
                     f"&order=created_at.desc&limit=500") or []
    out = []
    for r in rows:
        subj = (r.get("subject") or {}).get("name") or "General"
        out.append({"id": r["id"], "subject": subj, "subject_id": r.get("subject_id"),
                    "question_text": r.get("question_text", ""), "summary": r.get("summary", ""),
                    "source": r.get("source", "ask"), "created_at": r.get("created_at")})
    return out
```

- [ ] **Step 2: Add the delete kind to `delete_tree`**

In `delete_tree`, alongside the existing `elif kind == "answer":` branch, add:

```python
    elif kind == "saved_answer":
        sb_sql(f"delete from saved_answers where id={i};")
```
(`i` is the already-sanitized id local used by the other branches — reuse it verbatim.)

- [ ] **Step 3: Add the `/api/saved` route in the POST handler**

Next to the existing `elif p.path == "/api/tree":`-style routes (GET) and the delete route,
add a route that returns the saved list. Put it with the read routes:

```python
            elif p.path == "/api/saved":
                self._json({"saved": fetch_saved()})
```
The existing `/api/delete` route already dispatches `delete_tree(body["kind"], body["id"])`,
so `{"kind":"saved_answer","id":"<uuid>"}` works with no further change.

- [ ] **Step 4: Verify syntax + behavior**

Run:
```bash
cd /Users/pr3n3v/watch && python3 -c "import ast; ast.parse(open('ingestion/dashboard.py').read()); print('OK')"
```
Expected: `OK`. Then start the dashboard (`./start-dashboard.command` or
`cd ingestion && python3 dashboard.py`), insert a probe saved row (Task 1 Step 3), and:
```bash
curl -sS -X POST http://127.0.0.1:8765/api/saved -H 'Content-Type: application/json' -d '{}'
```
Expected: JSON `{"saved":[...]}` including the probe (subject `"General"`). Then delete via the
dashboard delete route:
```bash
curl -sS -X POST http://127.0.0.1:8765/api/delete -H 'Content-Type: application/json' \
  -d '{"kind":"saved_answer","id":"<probe-id>"}'
```
Expected: `{"ok": true}` (or the handler's success shape); confirm the row is gone.

- [ ] **Step 5: Commit**

```bash
git add ingestion/dashboard.py
git commit -m "feat(dashboard): fetch_saved, /api/saved, delete kind saved_answer"
```

---

### Task 5: Dashboard "Saved" tab (SPA)

**Files:**
- Modify: `ingestion/dashboard.py` (the embedded `PAGE` HTML/JS string)

**Interfaces:**
- Consumes: `/api/saved`, `/api/delete`.
- Produces: a "Saved" tab listing saved answers grouped by subject/General, each deletable.

- [ ] **Step 1: Add a tab button + panel to the PAGE HTML**

In the tab bar (where the "Content" and "Review" tab buttons are defined) add:
```html
<button id="tab-saved" onclick="showTab('saved')">Saved</button>
```
and a panel container near the other panels:
```html
<div id="panel-saved" style="display:none"></div>
```
(Match the existing tab show/hide convention used by `showTab`.)

- [ ] **Step 2: Add the render + delete JS**

```javascript
async function loadSaved(){
  const {saved} = await api('/api/saved', {});
  const groups = {};
  for(const r of saved){ (groups[r.subject] ||= []).push(r); }
  const el = document.getElementById('panel-saved');
  el.innerHTML = Object.keys(groups).sort().map(subj => `
    <h3>${subj} <span class="muted">(${groups[subj].length})</span></h3>
    ${groups[subj].map(r => `
      <div class="saved-row">
        <div><b>${escapeHtml(r.question_text)}</b></div>
        <div class="muted">${escapeHtml(r.summary)} · <i>${r.source}</i></div>
        <button onclick="delSaved('${r.id}')">Delete</button>
      </div>`).join('')}
  `).join('') || '<p class="muted">No saved answers yet.</p>';
}
async function delSaved(id){
  if(!confirm('Delete this saved answer? (does not touch the question bank)')) return;
  await api('/api/delete', {kind:'saved_answer', id});
  loadSaved();
}
```
Reuse the page's existing `api(path, body)` fetch helper and `escapeHtml` (if `escapeHtml`
does not exist, add `function escapeHtml(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}`).

- [ ] **Step 3: Wire `showTab('saved')` to call `loadSaved()`**

In the existing `showTab(name)` function, add: `if(name==='saved') loadSaved();`

- [ ] **Step 4: Verify in the browser**

Start the dashboard, insert two probe saved rows (one with a real `subject_id`, one `null`),
open `http://127.0.0.1:8765`, click **Saved**. Expected: two groups (the subject + "General"),
each row with question/summary/source and a Delete button. Click Delete on one → it disappears
and the canonical bank is unaffected (check the Content tab still shows all questions).

- [ ] **Step 5: Commit**

```bash
git add ingestion/dashboard.py
git commit -m "feat(dashboard): Saved tab to browse and delete saved answers"
```

---

## Phase 3 — Watch: Tap-to-Edit

### Task 6: Question tokenizer (pure, unit-tested)

**Files:**
- Create: `app/TutorBankWatch/Models/QuestionTokenizer.swift`
- Create: `app/TutorBankWatchTests/QuestionTokenizerTests.swift` (new unit-test target)
- Modify: `app/project.yml` (add the `TutorBankWatchTests` target + its scheme test action)

**Interfaces:**
- Produces:
  - `enum QToken: Identifiable { case fixed(String); case value(id: Int, text: String); var id: Int }`
  - `struct QuestionTokenizer { static func tokenize(_ s: String) -> [QToken]; static func reconstruct(_ tokens: [QToken]) -> String }`
  - `value` tokens carry a stable index `id` (0-based order of appearance) used as the edit key.

- [ ] **Step 1: Add the unit-test target to `project.yml`, then regenerate**

First inspect the current shape: `grep -n "TutorBankWatch:\|TutorBankWatchUITests:\|type:\|schemes:\|test:" app/project.yml`.
Add a unit-test target (adjust `deploymentTarget`/`bundleIdPrefix` to match the file's existing
values):

```yaml
  TutorBankWatchTests:
    type: bundle.unit-test
    platform: watchOS
    sources: [TutorBankWatchTests]
    dependencies:
      - target: TutorBankWatch
```
Ensure the `TutorBankWatch` scheme runs it — if `project.yml` has an explicit `schemes:` block,
add `TutorBankWatchTests` to that scheme's `test.targets`; if schemes are auto-generated, the
target is picked up automatically. Then:
```bash
cd /Users/pr3n3v/watch/app && xcodegen generate
```

- [ ] **Step 2: Write failing tests**

```swift
import XCTest
@testable import TutorBankWatch  // if the module name differs, match the app target's product module name

final class QuestionTokenizerTests: XCTestCase {
    private func values(_ s: String) -> [String] {
        QuestionTokenizer.tokenize(s).compactMap { if case let .value(_, t) = $0 { return t } else { return nil } }
    }
    func testNumbersAndOperators() {
        XCTAssertEqual(values("4x-2y+6z=8"), ["4","-","2","+","6","=","8"])
    }
    func testUnaryMinusIsPartOfNumber() {
        XCTAssertEqual(values("f(x) = -3x + 1"), ["-3","+","1"])  // '=' then unary -3
    }
    func testMatrixEntries() {
        XCTAssertEqual(values("rank of [[1, 2, 3], [2, 3, 4]]"), ["1","2","3","2","3","4"])
    }
    func testDecimalAndFraction() {
        XCTAssertEqual(values("area = 3.5 / 2"), ["3.5","/","2"])
    }
    func testReconstructIsIdentityWhenUnedited() {
        let s = "solve 4x-2y+6z=8 for x"
        XCTAssertEqual(QuestionTokenizer.reconstruct(QuestionTokenizer.tokenize(s)), s)
    }
    func testEditedValueReconstructs() {
        var toks = QuestionTokenizer.tokenize("x = 2")
        toks = toks.map { if case let .value(id, _) = $0, id == 0 { return .value(id: 0, text: "7") } else { return $0 } }
        XCTAssertEqual(QuestionTokenizer.reconstruct(toks), "x = 7")
    }
}
```

- [ ] **Step 3: Run tests to confirm they fail**

Run:
```bash
cd /Users/pr3n3v/watch/app
xcodebuild test -project TutorBank.xcodeproj -scheme TutorBankWatch \
  -destination 'platform=watchOS Simulator,id=BFF2EE35-2447-4F35-A9A5-957C4D0D4277' \
  -only-testing:TutorBankWatchTests/QuestionTokenizerTests 2>&1 | tail -15
```
Expected: FAIL — `QuestionTokenizer` not found.

- [ ] **Step 4: Implement the tokenizer**

```swift
import Foundation

enum QToken: Identifiable {
    case fixed(String)
    case value(id: Int, text: String)
    var id: Int { if case let .value(id, _) = self { return id } else { return -1 } }
}

struct QuestionTokenizer {
    private static let operators: Set<Character> = ["+", "−", "-", "×", "÷", "*", "/", "=", "^"]
    private static let digits: Set<Character> = Set("0123456789")

    static func tokenize(_ s: String) -> [QToken] {
        var out: [QToken] = []
        var fixedBuf = ""
        var vid = 0
        func flushFixed() { if !fixedBuf.isEmpty { out.append(.fixed(fixedBuf)); fixedBuf = "" } }
        // Track the last non-space emitted meaning, to resolve unary minus.
        func lastMeaningfulIsOperatorOrOpen() -> Bool {
            for tok in out.reversed() {
                switch tok {
                case .value: return false
                case .fixed(let f):
                    let t = f.trimmingCharacters(in: .whitespaces)
                    if t.isEmpty { continue }
                    let c = t.last!
                    return c == "(" || c == "[" || c == "," || operators.contains(c)
                }
            }
            return true // start of string
        }

        let chars = Array(s)
        var i = 0
        while i < chars.count {
            let c = chars[i]
            // Unary minus: '-' that begins a number (preceded by start/open/operator/comma).
            if (c == "-" || c == "−"), i + 1 < chars.count, digits.contains(chars[i + 1]),
               (fixedBuf.trimmingCharacters(in: .whitespaces).isEmpty ? lastMeaningfulIsOperatorOrOpen()
                : { let t = fixedBuf.trimmingCharacters(in: .whitespaces); let k = t.last!; return k == "(" || k == "[" || k == "," || operators.contains(k) }()) {
                flushFixed()
                var num = "-"
                i += 1
                while i < chars.count, digits.contains(chars[i]) || chars[i] == "." { num.append(chars[i]); i += 1 }
                out.append(.value(id: vid, text: num)); vid += 1
                continue
            }
            if digits.contains(c) {
                flushFixed()
                var num = ""
                while i < chars.count, digits.contains(chars[i]) || chars[i] == "." { num.append(chars[i]); i += 1 }
                out.append(.value(id: vid, text: num)); vid += 1
                continue
            }
            if operators.contains(c), c != "-", c != "−" {   // standalone operator (binary)
                flushFixed()
                out.append(.value(id: vid, text: String(c))); vid += 1
                i += 1
                continue
            }
            if c == "-" || c == "−" {   // binary minus (not unary): its own operator chip
                flushFixed()
                out.append(.value(id: vid, text: String(c))); vid += 1
                i += 1
                continue
            }
            fixedBuf.append(c); i += 1
        }
        flushFixed()
        return out
    }

    static func reconstruct(_ tokens: [QToken]) -> String {
        tokens.map { tok in
            switch tok { case .fixed(let f): return f; case .value(_, let t): return t }
        }.joined()
    }
}
```

- [ ] **Step 5: Ensure the new source file is in the project**

If `app/project.yml` lists sources by folder glob, files under `TutorBankWatch/Models/` are
picked up automatically — regenerate: `cd app && xcodegen generate`. If it lists individual
files, add `TutorBankWatch/Models/QuestionTokenizer.swift`, then `xcodegen generate`. (The test
target + test file were added in Step 1.)

- [ ] **Step 6: Run tests to confirm they pass**

Run the same `xcodebuild test ... -only-testing:TutorBankWatchTests/QuestionTokenizerTests`
command from Step 3. Expected: all 6 tests PASS. If `testUnaryMinusIsPartOfNumber` fails, the
unary rule needs the exact fix shown in Step 4 — do not weaken the test.

- [ ] **Step 7: Commit**

```bash
git add app/TutorBankWatch/Models/QuestionTokenizer.swift app/TutorBankWatchTests/QuestionTokenizerTests.swift app/project.yml
git commit -m "feat(watch): question tokenizer with unary-minus handling + tests"
```

---

### Task 7: Wrapping FlowLayout

**Files:**
- Create: `app/TutorBankWatch/Views/FlowLayout.swift`

**Interfaces:**
- Produces: `struct FlowLayout: Layout` with an `init(spacing: CGFloat = 4)` that lays out
  subviews left-to-right, wrapping to new rows within the proposed width.

- [ ] **Step 1: Implement the layout**

```swift
import SwiftUI

/// Left-to-right wrapping layout (watchOS has no native flow layout). Used to lay out
/// value chips + fixed text fragments in ValueEditHubView.
struct FlowLayout: Layout {
    var spacing: CGFloat = 4

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxW = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowH: CGFloat = 0, totalW: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > maxW, x > 0 { x = 0; y += rowH + spacing; rowH = 0 }
            x += s.width + spacing; rowH = max(rowH, s.height); totalW = max(totalW, x)
        }
        return CGSize(width: min(totalW, maxW), height: y + rowH)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let maxW = bounds.width
        var x: CGFloat = bounds.minX, y: CGFloat = bounds.minY, rowH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > bounds.minX + maxW, x > bounds.minX { x = bounds.minX; y += rowH + spacing; rowH = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing; rowH = max(rowH, s.height)
        }
    }
}
```

- [ ] **Step 2: Build to verify it compiles**

Run:
```bash
cd /Users/pr3n3v/watch/app
xcodebuild -project TutorBank.xcodeproj -scheme TutorBankWatch \
  -destination 'platform=watchOS Simulator,id=BFF2EE35-2447-4F35-A9A5-957C4D0D4277' \
  -derivedDataPath /tmp/tb-dd CODE_SIGNING_ALLOWED=NO build 2>&1 | tail -4
```
Expected: `** BUILD SUCCEEDED **` (after `xcodegen generate` if needed).

- [ ] **Step 3: Commit**

```bash
git add app/TutorBankWatch/Views/FlowLayout.swift app/project.yml
git commit -m "feat(watch): wrapping FlowLayout for value chips"
```

---

### Task 8: Single-cell keypad editor

**Files:**
- Create: `app/TutorBankWatch/Views/ValueEditKeypadView.swift`

**Interfaces:**
- Consumes: nothing new.
- Produces: `struct ValueEditKeypadView: View { init(initial: String, onDone: @escaping (String) -> Void) }`
  — shows the working value, a math keypad, Scribble field, `⌫`/`C`; calls `onDone(newValue)`
  and dismisses when the user confirms.

- [ ] **Step 1: Implement the editor**

```swift
import SwiftUI

/// Focused editor for ONE value chip: math keypad + Scribble + erase.
struct ValueEditKeypadView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var text: String
    let onDone: (String) -> Void

    init(initial: String, onDone: @escaping (String) -> Void) {
        _text = State(initialValue: initial)
        self.onDone = onDone
    }

    private let rows: [[String]] = [
        ["7","8","9","(",")"],
        ["4","5","6","[","]"],
        ["1","2","3","/","^"],
        ["0",".",",","±","⌫"],
        ["+","−","×","÷","="],
    ]

    var body: some View {
        ScrollView {
            VStack(spacing: 6) {
                TextField("value", text: $text)               // Scribble/dictation path
                    .font(.system(.title3, design: .monospaced))
                    .multilineTextAlignment(.center)
                ForEach(rows.indices, id: \.self) { r in
                    HStack(spacing: 4) {
                        ForEach(rows[r], id: \.self) { key in
                            Button(key) { tap(key) }
                                .buttonStyle(.bordered)
                                .frame(maxWidth: .infinity)
                        }
                    }
                }
                HStack {
                    Button("Clear", role: .destructive) { text = "" }.buttonStyle(.bordered)
                    Button("Done") { onDone(text); dismiss() }.buttonStyle(.borderedProminent)
                }
            }
            .padding(.horizontal, 2)
        }
        .navigationTitle("Edit value")
    }

    private func tap(_ key: String) {
        switch key {
        case "⌫": if !text.isEmpty { text.removeLast() }
        case "±":
            if text.hasPrefix("-") { text.removeFirst() } else { text = "-" + text }
        default: text += key
        }
    }
}
```

- [ ] **Step 2: Build to verify it compiles**

Run the Task 7 Step 2 `xcodebuild ... build` command. Expected: `** BUILD SUCCEEDED **`.

- [ ] **Step 3: Commit**

```bash
git add app/TutorBankWatch/Views/ValueEditKeypadView.swift app/project.yml
git commit -m "feat(watch): single-cell math keypad editor"
```

---

### Task 9: Hub view (chips + Solve) replacing ValueSwapView

**Files:**
- Create: `app/TutorBankWatch/Views/ValueEditHubView.swift`
- Delete: `app/TutorBankWatch/Views/ValueSwapView.swift`
- Modify: `app/TutorBankWatch/Services/AskService.swift` (add params — see Task 10 interfaces)

**Interfaces:**
- Consumes: `QuestionTokenizer`, `FlowLayout`, `ValueEditKeypadView`, `LiveAnswerModel`,
  `LiveResultView`, `Question` (has `.text`, `.isCode`, and its subject id — see note).
- Produces: `struct ValueEditHubView: View { init(question: Question, subjectId: String) }`.

Note on subject id: `Question` must expose the owning subject's id for saving. Confirm how the
watch knows a question's subject (via the `Bank` nav hierarchy). Pass `subjectId` down from
`TutorRootView` when navigating (Subject → … → Question), matching how the app already threads
subject context. If `Question` has no subject id, thread it as an explicit `subjectId` argument
from the subject screen (do NOT add a DB lookup).

- [ ] **Step 1: Implement the hub**

```swift
import SwiftUI

struct ValueEditHubView: View {
    let question: Question
    let subjectId: String

    @State private var tokens: [QToken]
    @State private var editing: (id: Int, text: String)?   // non-nil while the keypad is up
    @State private var editedIds: Set<Int> = []
    @StateObject private var model = LiveAnswerModel()
    @State private var showResult = false

    init(question: Question, subjectId: String) {
        self.question = question
        self.subjectId = subjectId
        _tokens = State(initialValue: QuestionTokenizer.tokenize(question.text))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                Text("Tap a value to change it, then Solve.")
                    .font(.caption2).foregroundStyle(.secondary)
                FlowLayout(spacing: 4) {
                    ForEach(Array(tokens.enumerated()), id: \.offset) { _, tok in
                        switch tok {
                        case .fixed(let f):
                            Text(f).font(.footnote)
                        case .value(let id, let t):
                            Button(t) { editing = (id, t) }
                                .buttonStyle(.bordered)
                                .tint(editedIds.contains(id) ? .accentColor : .secondary)
                        }
                    }
                }
                NavigationLink(isActive: $showResult) {
                    LiveResultView(title: "Result", model: model, retry: solve, isCode: question.isCode)
                } label: { EmptyView() }.hidden()

                Button { solve() } label: {
                    Label("Solve", systemImage: "function")
                }
                .buttonStyle(.borderedProminent)
                .disabled(model.isLoading)
            }
            .padding(.horizontal, 4)
        }
        .navigationTitle("Change the numbers")
        .sheet(item: Binding(get: { editing.map { EditingCell(id: $0.id, text: $0.text) } },
                             set: { if $0 == nil { editing = nil } })) { cell in
            NavigationStack {
                ValueEditKeypadView(initial: cell.text) { newText in
                    tokens = tokens.map { tok in
                        if case let .value(id, _) = tok, id == cell.id { return .value(id: id, text: newText) }
                        return tok
                    }
                    editedIds.insert(cell.id)
                    editing = nil
                }
            }
        }
    }

    private struct EditingCell: Identifiable { let id: Int; let text: String }

    private func solve() {
        let modified = QuestionTokenizer.reconstruct(tokens)
        showResult = true
        model.start(prompt: "Solve this exam question fully: \(modified)",
                    mode: .solve, context: question.text,
                    subjectId: subjectId, source: "tap_edit")
    }
}
```

- [ ] **Step 2: Delete the old ValueSwapView and repoint its caller**

```bash
rm app/TutorBankWatch/Views/ValueSwapView.swift
```
(The caller is updated in Task 10. `xcodegen generate` after deletion.)

- [ ] **Step 3: Build (will fail until Task 10 updates `LiveAnswerModel.start`)**

Run the Task 7 Step 2 build. Expected: FAIL referencing `start(...subjectId:source:)` — that
signature is added in Task 10. This task and Task 10 land together; commit after Task 10 builds.

- [ ] **Step 4: (Deferred commit — see Task 10 Step 5.)**

---

### Task 10: Thread `subjectId`/`source` through AskService + LiveAnswerModel; wire the button

**Files:**
- Modify: `app/TutorBankWatch/Services/AskService.swift`
- Modify: `app/TutorBankWatch/Views/LiveAnswerView.swift`
- Modify: `app/TutorBankWatch/Views/AnswerView.swift`
- Modify: `app/TutorBankWatch/Views/AskView.swift`

**Interfaces:**
- Produces:
  - `AskService.ask(prompt:mode:context:subjectId:source:) async throws -> AskReply`
  - `LiveAnswerModel.start(prompt:mode:context:subjectId:source:)`
  - `AskService.fetchSaved(subjectId: String) async throws -> [SavedAnswer]` (used by Task 11).
  - `struct SavedAnswer: Codable, Identifiable { id, questionText, summary, answer, model, source, createdAt }`.

- [ ] **Step 1: Extend `AskService.ask` to send the new fields**

In `AskService.swift`, add parameters and include them in the POST body:

```swift
static func ask(prompt: String, mode: AskMode, context: String?,
                subjectId: String? = nil, source: String = "ask") async throws -> AskReply {
    // ... existing request setup ...
    var payload: [String: Any] = ["prompt": prompt, "mode": mode.rawValue]
    if let context { payload["context"] = context }
    if let subjectId { payload["subject_id"] = subjectId }
    payload["source"] = source
    // ... existing encode/send/decode ...
}
```
(Match the existing body-construction style; if it uses a `Codable` request struct, add
`subject_id` and `source` to that struct instead.)

- [ ] **Step 2: Extend `LiveAnswerModel.start` to pass them through**

In `LiveAnswerView.swift`, update `start` and its stored task call:

```swift
func start(prompt: String, mode: AskMode, context: String?,
           subjectId: String? = nil, source: String = "ask") {
    task?.cancel()
    task = Task { await run(prompt: prompt, mode: mode, context: context,
                            subjectId: subjectId, source: source) }
}
private func run(prompt: String, mode: AskMode, context: String?,
                 subjectId: String?, source: String) async {
    // ... existing body, but call:
    let result = try await AskService.ask(prompt: prompt, mode: mode, context: context,
                                          subjectId: subjectId, source: source)
    // ... rest unchanged ...
}
```

- [ ] **Step 3: Replace the "Change values" entry in AnswerView**

In `AnswerView.swift`, the `actions` block currently gates on `question.hasVariables` and
pushes `ValueSwapView`. Replace with an always-available entry (any question with a value):

```swift
if !QuestionTokenizer.tokenize(question.text).allSatisfy({ if case .value = $0 { return false } else { return true } }) {
    NavigationLink {
        ValueEditHubView(question: question, subjectId: subjectId)
    } label: { Label("Change the numbers", systemImage: "slider.horizontal.3") }
    .buttonStyle(.bordered)
}
```
`AnswerView` must receive `subjectId`; add `let subjectId: String` to `AnswerView` and pass it
at the call site in `TutorRootView` (Task 12 threads it). Update `AskView(contextQuestion:)`
call in the same block to also pass `subjectId` so "Ask about this" saves under the subject
(Task 11 uses it).

- [ ] **Step 4: Pass subjectId + source from AskView**

In `AskView.swift`, add `let subjectId: String?` and pass it in `send()`:
```swift
model.start(prompt: prompt, mode: .chat, context: contextQuestion?.text,
            subjectId: subjectId, source: contextQuestion == nil ? "chat" : "ask")
```
`contextQuestion == nil` is the free-chat case → `subjectId` should be `nil` there → General.

- [ ] **Step 5: Build, run the tokenizer tests, commit Tasks 9+10 together**

Run `xcodegen generate` then the Task 7 build and the Task 6 test command. Expected: build
SUCCEEDED, tokenizer tests still PASS. Commit:
```bash
git add app/TutorBankWatch app/project.yml
git commit -m "feat(watch): tap-to-edit hub + thread subjectId/source through ask"
```

---

## Phase 4 — Watch: Saved Answers

### Task 11: `fetchSaved` + SavedAnswersListView

**Files:**
- Modify: `app/TutorBankWatch/Services/AskService.swift` (add `fetchSaved` + `SavedAnswer` — declared in Task 10 interfaces)
- Create: `app/TutorBankWatch/Views/SavedAnswersListView.swift`

**Interfaces:**
- Consumes: `AskService.fetchSaved`, `SummaryText`, `WorkingView`.
- Produces: `struct SavedAnswersListView: View { init(subjectId: String?, title: String) }`
  (`subjectId == nil` → the `"general"` bucket).

- [ ] **Step 1: Implement `fetchSaved` + `SavedAnswer` in AskService**

```swift
struct SavedAnswer: Codable, Identifiable {
    let id: String
    let questionText: String
    let summary: String
    let answer: String?
    let model: String?
    let source: String
    let createdAt: String
}

extension AskService {
    static func fetchSaved(subjectId: String?) async throws -> [SavedAnswer] {
        struct Resp: Codable { let saved: [SavedAnswer] }
        let body = ["subject_id": subjectId ?? "general"]
        // Reuse the same POST-to-Edge-Function helper `ask` uses, but hitting `/saved`.
        // Decoder uses .convertFromSnakeCase (matches SyncService).
        let data = try await postToFunction("saved", body: body)
        return try snakeDecoder().decode(Resp.self, from: data).saved
    }
}
```
If `AskService` has no reusable `postToFunction`/`snakeDecoder`, factor the URLRequest builder
`ask` already uses into a small private helper and reuse it here (DRY). Keep the `X-App-Secret`
header and base URL identical to `ask`.

- [ ] **Step 2: Implement the list + detail view**

```swift
import SwiftUI

struct SavedAnswersListView: View {
    let subjectId: String?
    let title: String
    @State private var items: [SavedAnswer] = []
    @State private var error: String?

    var body: some View {
        List {
            if let error { Text(error).font(.footnote).foregroundStyle(.red) }
            if items.isEmpty && error == nil {
                Text("No saved answers yet.").font(.footnote).foregroundStyle(.secondary)
            }
            ForEach(items) { item in
                NavigationLink {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(item.questionText).font(.caption).foregroundStyle(.secondary)
                            SummaryText(summary: item.summary)
                            if let a = item.answer, !a.isEmpty { Divider(); WorkingView(working: a) }
                        }
                    }.navigationTitle("Saved")
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(item.summary).font(.footnote).lineLimit(2)
                        Text(item.questionText).font(.caption2).foregroundStyle(.secondary).lineLimit(1)
                    }
                }
            }
        }
        .navigationTitle(title)
        .task {
            do { items = try await AskService.fetchSaved(subjectId: subjectId) }
            catch { self.error = "Couldn't load saved answers." }
        }
    }
}
```

- [ ] **Step 3: Build to verify it compiles**

`xcodegen generate` then the Task 7 build. Expected: `** BUILD SUCCEEDED **`.

- [ ] **Step 4: Commit**

```bash
git add app/TutorBankWatch app/project.yml
git commit -m "feat(watch): fetchSaved + SavedAnswersListView (read-only)"
```

---

### Task 12: "Saved Answers" row per subject + "General" row

**Files:**
- Modify: `app/TutorBankWatch/Views/TutorRootView.swift`

**Interfaces:**
- Consumes: `SavedAnswersListView`, the subject list model (`Bank`/`BankStore`).
- Produces: navigation entries; threads `subjectId` down to `AnswerView`/`ValueEditHubView`.

- [ ] **Step 1: Add the "Saved Answers" row in the subject detail**

In the view that lists a subject's units (inside `TutorRootView`), append after the units:

```swift
NavigationLink {
    SavedAnswersListView(subjectId: subject.id, title: "Saved Answers")
} label: { Label("Saved Answers", systemImage: "bookmark") }
```
Ensure every `AnswerView`/`ValueEditHubView` navigation from this subject passes
`subjectId: subject.id` (Task 10 Step 3 added the parameter).

- [ ] **Step 2: Add the "General" row on the Subjects list**

At the bottom of the top-level Subjects list, append:
```swift
NavigationLink {
    SavedAnswersListView(subjectId: nil, title: "General")
} label: { Label("General", systemImage: "tray") }
```

- [ ] **Step 3: Build + confirm the tokenizer tests still pass**

`xcodegen generate`, then the Task 7 build and the Task 6 test command. Expected: build
SUCCEEDED, tests PASS.

- [ ] **Step 4: Commit**

```bash
git add app/TutorBankWatch app/project.yml
git commit -m "feat(watch): Saved Answers row per subject + General row"
```

---

## Phase 5 — Integration verification (simulator)

### Task 13: End-to-end on the SE 3 44mm sim

**Files:** none (verification only).

- [ ] **Step 1: Boot, build, install, launch**

```bash
cd /Users/pr3n3v/watch
SIM=BFF2EE35-2447-4F35-A9A5-957C4D0D4277
DD=/tmp/tb-simdd
xcrun simctl boot $SIM 2>/dev/null; open -a Simulator
xcodebuild -project app/TutorBank.xcodeproj -scheme TutorBankWatch \
  -destination "platform=watchOS Simulator,id=$SIM" -derivedDataPath $DD \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
xcrun simctl install $SIM "$DD/Build/Products/Debug-watchsimulator/TutorBankWatch.app"
xcrun simctl launch $SIM com.pr3n3v.notesbank688c9257.watchkitapp
```
Expected: app launches (a pid prints).

- [ ] **Step 2: Tap-edit end-to-end**

Manually in the sim: long-press the timer → EM2 → Unit 1 → a `solve` question → "Change the
numbers" → tap 2–3 value chips (edited chips turn accent-colored) → Solve. Expected: an answer
renders. Then verify the branch was saved and the canonical rows are untouched:
```bash
set -a && source .env && set +a
curl -sS "$SUPABASE_URL/rest/v1/saved_answers?source=eq.tap_edit&select=question_text,summary&order=created_at.desc&limit=1" \
  -H "apikey: $SUPABASE_SERVICE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY"
```
Expected: one row whose `question_text` contains the CHANGED numbers. Confirm the original
question row is unchanged (its `answers` summary is still the verified one).

- [ ] **Step 3: Saved Answers + General**

In the sim: open the subject's "Saved Answers" → the tap_edit branch shows. Do an "Ask about
this" and a free-chat "Ask a question"; confirm the first appears under the subject and the
second under "General". Then delete the tap_edit branch in the dashboard Saved tab and re-open
the watch section → it's gone; the question bank is intact.

- [ ] **Step 4: Render-safety spot check**

Confirm an edited value like `x^2` or `a_(n+1)` shows as ASCII (no ☐ boxes) on the sim,
per the Global Constraints.

- [ ] **Step 5: Commit any fixups**

```bash
git add -A && git commit -m "test(watch): tap-edit + saved-answers verified on sim" || echo "nothing to commit"
```

---

## Self-Review Notes (author)

- Spec §2 (tap-edit) → Tasks 6–10, 13. §3 (saved answers) → Tasks 1–5, 11–12, 13.
- Every `/ask` caller now passes `subjectId`/`source` (Tasks 9, 10); free-chat → `nil`/`chat`.
- Type names consistent: `QToken`, `QuestionTokenizer.tokenize/reconstruct`, `SavedAnswer`,
  `AskService.ask(...subjectId:source:)`, `AskService.fetchSaved`, `LiveAnswerModel.start(...subjectId:source:)`.
- Non-destructive branching enforced: no task writes `questions`/`answers`; the tap-edit
  result only ever inserts into `saved_answers` via `/ask`.
