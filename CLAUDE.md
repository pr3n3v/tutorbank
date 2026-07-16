# TutorBank — Personal Question-Bank Assistant (Watch + iPhone + Backend)

> **Read me first (Claude Code):** This file is the single source of truth for this project.
> It encodes decisions already made with the user. Do not re-litigate them; ask only when
> something here is genuinely ambiguous or contradicts reality at build time.

---

## 1. What this is

A personal tutoring aid for the user, who teaches his younger brother. Known assignment
questions are **pre-solved once, verified, and cached** in a database. An Apple Watch SE 3
app shows a **boxed final answer at a glance, with the full exam-ready working one scroll
below**. A companion iPhone app holds the same content with more room, big diagrams, and
content management. A small backend proxies live AI queries.

**Prime directive for output style (two tiers, both mandatory):**
- **`summary` — the glance line.** ONE line: the boxed final answer, exam-ready, Unicode
  math. This is what the user reads mid-lesson without breaking eye contact. No steps.
- **`answer` — the full exam-scoring solution.** The complete worked answer a student
  writes to earn **full marks**: every step, the method named, the final answer boxed.
  Engineering answers are long and **the marks are in the working** — so `answer` is a
  first-class deliverable, NOT background storage. It must be exam-complete, never a sketch.

The watch shows the `summary` big at the top, then the full `answer` scrollable beneath it
(§7). The one-liner is the glance; the working is what you actually write/teach. This
matters most for **EM2** (derivations) and other solve/proof questions where a bare result
earns zero marks.

### Non-goals
- No public release. Personal install via Xcode (free provisioning, 7-day re-sign).
- No web frontend for the watch. watchOS cannot reliably render web apps — **native only**.
- No diffusion/image-generation models for diagrams. Diagrams are rendered
  deterministically with Graphviz. (Vision models MAY be used later for *reading*
  photographed diagrams — see v2 backlog.)

---

## 2. Architecture (locked)

```
[Assignment PDFs/photos]
        │  (local ingestion script, run on the user's Mac)
        ▼
[Ingestion pipeline: parse → extract questions → DeepSeek generate → verify → render diagrams]
        │
        ▼
[Supabase Postgres]  ◄────────── content additions are DATA ONLY, never app changes
        │
        ├── Supabase Edge Function  /sync   → full question bank JSON (watch/phone cache)
        └── Supabase Edge Function  /ask    → live DeepSeek proxy (ad-hoc chat, value swaps)
        ▲
        │  HTTPS + shared-secret header
[watchOS app (SwiftUI)] ↔ [iOS companion app]
```

- **Database + backend host:** Supabase (already provisioned by user). Edge Functions hold
  the DeepSeek key. Alternative host if ever needed: Cloudflare Workers. Do not use
  Render/Railway free tiers (cold-start / trial limitations).
- **Offline-first:** the watch and phone cache the entire bank locally. Cached answers must
  open with **zero network**. Only `/ask` (live chat, value swaps) needs connectivity.
- **Ingestion runs locally** on the Mac (Python script), not hosted. It writes to
  Supabase with the service-role key from a local `.env` (never committed).

---

## 3. Data model (Supabase / Postgres)

Create via migration SQL. Names are locked; add columns freely, don't rename these.

```
subjects
  id uuid pk
  name text                -- "Engineering Mathematics 2"
  code text unique         -- "EM2", "FLAT", "JAVA", "AJAVA", "DAA"
  format_profile jsonb     -- per-subject prompting + formatting rules (see §5)

assignments
  id uuid pk
  subject_id uuid fk -> subjects
  title text
  number int
  source_file text         -- provenance (original filename)

units
  id uuid pk
  subject_id uuid fk -> subjects
  name text                -- navigation layer: "choose unit"
  position int

questions
  id uuid pk
  unit_id uuid fk -> units
  assignment_id uuid fk -> assignments
  text text                -- full original question
  qtype text               -- 'concept' | 'solve' | 'proof' | 'diagram' | 'predict_output' | 'program'
  variables jsonb          -- nullable; e.g. [{"name":"a","default":3}] for value-swap templates
  position int

answers
  id uuid pk
  question_id uuid fk -> questions
  variant text default 'default'   -- 'default' or serialized swapped values e.g. 'a=5'
  summary text             -- ★ THE GLANCE LINE. One line, boxed final answer, Unicode math.
  answer text              -- ★ FULL EXAM-SCORING solution: every step, method, boxed final.
                           --   Shown on watch (scroll) AND phone. First-class, not storage.
  final_answer text        -- boxed final result where applicable
  diagram_dot text         -- nullable; Graphviz DOT source
  diagram_png_watch text   -- nullable; storage path, sized for SE 3 (see §6)
  diagram_png_phone text   -- nullable; storage path, full-size render
  followups jsonb          -- nullable, OPTIONAL: [{q, a}] likely student follow-ups (a = one line; shape matches §5 contract)
  model_used text
  confidence numeric       -- model self-rating 0–1
  verified boolean default false   -- user flips after eyeballing; UI surfaces unverified first
  created_at timestamptz
```

**Security (locked):** RLS on all tables; anon key has no direct table access. Clients talk
only to Edge Functions. Both functions require header `X-App-Secret: <random 32+ chars>`
checked against an env var. DeepSeek account stays **prepaid-only** so a leaked URL can't
run up unbounded cost.

---

## 4. Subjects (initial content)

| code  | name                                  | notes for format_profile |
|-------|---------------------------------------|--------------------------|
| FLAT  | Finite Languages & Automata Theory    | diagram-heavy; DOT for automata; formal one-liners (regex / 5-tuple / grammar / "not regular — pumping lemma") |
| JAVA  | Programming in Java                   | split by qtype, see below |
| AJAVA | Advanced Programming in Java          | same as JAVA |
| EM2   | Engineering Mathematics 2             | one-line result in Unicode math, e.g. `∫x·eˣ dx = eˣ(x−1) + C` |
| DAA   | Design & Analysis of Algorithms       | `O(·)` bounds, recurrence solutions, algorithm name + one-line core idea |

**Java split (locked):**
- `predict_output` → summary = the exact program output, one line. Ideal glance case.
- `program` → summary = the ONE key line/idea (e.g. `c[i][j] += a[i][k]*b[k][j]` — triple
  loop). The **full compilable program is the exam answer** and lives in `answer` — shown
  on the watch as a scrollable monospaced block (§7a) and full on the phone. The *summary*
  is never the whole program (that can't glance), but the program itself must be present
  and complete.

---

## 5. Generation pipeline (DeepSeek)

### Models — IMPORTANT, time-sensitive
- Use **`deepseek-v4-pro`** (thinking mode) for answer **generation** (accuracy).
- Use **`deepseek-v4-flash`** for **live** `/ask` queries (speed).
- Legacy names `deepseek-chat` / `deepseek-reasoner` are deprecated (discontinued
  2026-07-24). **Do not use them.** API is OpenAI-compatible at `https://api.deepseek.com`.
- Verify exact model strings against DeepSeek docs at build time; if they've moved again,
  update here and in one config constant — model name must live in ONE place.

### Per-question generation call
One structured call per question. System prompt = base rules + the subject's
`format_profile`. **Response must be strict JSON** (no prose, no markdown fences):

```json
{
  "summary": "one exam-ready line: the boxed final answer, Unicode math (∫ ² √ δ →), no steps",
  "answer": "FULL exam-scoring worked solution: every step, method named, final answer boxed",
  "final_answer": "boxed final result or null",
  "diagram_dot": "graphviz DOT or null",
  "followups": [{"q": "...", "a": "one line"}],
  "confidence": 0.0
}
```

Base system-prompt rules (apply to every subject):
- Role: expert tutor preparing answers a teacher will deliver to a student who must
  reproduce them in an exam and **score full marks**. Correct, complete, and rigorous.
- `answer` is the primary deliverable: the COMPLETE worked solution as written on an exam
  sheet — every step shown, the method/rule named, intermediate results kept, the final
  answer boxed. Do NOT abbreviate or skip steps; the marks are in the working. It is NOT
  "background storage." Match the length the question deserves — long is fine, thin is not.
- `summary` is the glance line drawn FROM that solution: ONE line, the boxed final answer
  only, no preamble, no "we get", no steps. It must be consistent with `answer`'s result.
- Math in Unicode, not LaTeX, in `summary`. Full LaTeX allowed inside `answer`.
- Automata/graphs → emit `diagram_dot` (never ASCII art, never coordinates-by-hand SVG).
- Show the worked steps in `answer`, but never include model chain-of-thought / "thinking"
  meta-commentary — `answer` is the clean solution a student writes, not your reasoning log.

### Verification (locked)
1. **Computational answers (EM2, parts of DAA):** re-check symbolically with **SymPy**
   (integrals, derivatives, Laplace, series, recurrences) at ingestion time. Mismatch →
   regenerate once, then flag.
2. **Non-computational (proofs, theory, code):** independent second-model cross-check
   (call `deepseek-v4-pro` again with a "verify this answer, reply VALID/INVALID+reason"
   prompt, or another provider if configured). Disagreement → flag.
3. Everything lands with `verified=false`; the iPhone app surfaces unverified answers for
   the user to eyeball and flip. Low `confidence` sorts first.

### Value-swap variants
- Questions with `variables` are stored as templates.
- Pre-bake the obvious variants at ingestion (e.g. a ∈ {1,2,3,5}) as extra `answers` rows
  so most swaps are still cache hits.
- Novel swap at runtime → watch numeric input → `/ask` live call (v4-pro for solve-type) →
  result may be cached back.

---

## 6. Diagrams (locked decisions)

- The watch **cannot render SVG** (no runtime SVG support in SwiftUI, no WebView on
  watchOS; SVGKit/SDWebImage SVG paths are broken there). **Ship PNG.**
- Ingestion renders DOT with Graphviz twice:
  - **Phone PNG:** full size, no constraints.
  - **Watch PNG:** target the user's SE 3 — **44 mm, 368×448** (resolved, see §12). Render
    at 2× and downscale for crispness. Thick strokes, high contrast, minimum font ~28 pt
    at 2×.
- **State-count rule:** ≤5 states → watch PNG is the diagram. >5 states → watch gets the
  formal one-liner in `summary` (+ optionally a rendered transition-table PNG, which packs
  more info per pixel); full diagram is phone-only.

---

## 7. Apps (SwiftUI)

One Xcode project, **one bundle ID**, two targets: iOS companion + watchOS app.
(Free-provisioning limit is 3 apps/device and 7-day profiles — so everything ships as ONE
app. Future modules (health analytics, quick capture) join this same app/backend later;
keep module boundaries clean.)

### watchOS app
- **Landing screen = a fully functional study-session timer.** This is the disguise: on a
  tutor's wrist it is boring and plausible. Includes start/pause/reset and actually works.
- **Secret entry** to tutor UI: long-press on the timer face (fallback: Digital Crown
  rotation pattern). When app backgrounds/deactivates → auto-return to timer screen.
- Tutor UI navigation: **Subject → Unit → Question → Answer** (all list-driven from cache).
- **Answer screen (top → bottom):**
  1. `summary` — the boxed final answer, large type (the glance).
  2. diagram PNG if present.
  3. **Full worked solution** — `answer`, exam-complete, scrollable. This is the marks;
     it lives on the watch too, not just the phone. Rendered as readable steps (see §7a).
  4. **Change values** — if `variables` exist, a compact numeric input ("a = ? (was 3)")
     → live solve (§5 value-swap). Re-solving returns a fresh `summary` + full `answer`.
  5. **Ask about this** — an affordance below the answer → `/ask` with the question as
     context, for a follow-up or an alternative phrasing. Reply is itself boxed-answer +
     working (same two-tier shape), scrollable.
- **Chat tab:** dictation/Scribble → `/ask` → boxed answer + full working (scrollable),
  same two-tier output as cached answers. Not one-liners — exam-ready.
- **Cache:** on launch/sync, pull `/sync` JSON + watch PNGs into local storage
  (`FileManager`/SwiftData). All cached content opens instantly offline.
- Complication + Siri App Intent that deep-link straight into the tutor UI (they count as
  intentional entry, so they bypass the timer screen).

### 7a. Rendering the full worked solution on the watch
The `answer` is exam-complete and therefore long — the small screen handles it by
**scrolling**, not by truncating. Rules:
- Math renders as **Unicode plain text** (same charset as `summary`); no LaTeX engine and
  no WebView on watchOS, so `answer` must be Unicode-legible as-is. If a step is only
  expressible in LaTeX, the generator must also carry a Unicode rendering (the LaTeX stays
  for the phone's richer view).
- Code / `predict_output` steps render in a **monospaced** block.
- Steps are newline-separated so they wrap cleanly; keep each step to one idea per line.
- The boxed `summary` stays pinned at the top as the glance; the working scrolls below.
- Very wide artifacts (large tables, big DP grids) follow §6 — rendered to a PNG rather
  than crammed into text.

### iOS companion app
- Full answer view (`answer`, `final_answer`, LaTeX/rich rendering, full-size diagrams).
- Verification queue: unverified/low-confidence answers → read → mark `verified`.
- Content browser (subjects/assignments/units/questions) and manual edit affordances.
- Sync trigger + connection status to Supabase.

### watchOS platform gotchas (respect these)
- No WKWebView. No localStorage-style web persistence. No side-button remapping.
- App suspends when screen sleeps — resume state gracefully.
- Test on watchOS 26 simulator + the user's physical SE 3.

---

## 8. Repo layout

```
/backend
  /supabase
    /migrations          -- schema SQL
    /functions/sync      -- Edge Function: bank JSON for clients
    /functions/ask       -- Edge Function: DeepSeek proxy (flash default, pro for solves)
/ingestion
  ingest.py              -- parse files → questions → generate → verify → render → insert
  /prompts               -- base + per-subject format_profile prompt fragments
  /samples               -- user's assignment files land here (PENDING UPLOAD; gitignored)
/app
  TutorBank.xcodeproj    -- iOS + watchOS targets
/docs
  SETUP.md               -- one-time setup: secrets, Supabase, Xcode signing, weekly re-sign
```

`.env` (local only, never committed): `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
`DEEPSEEK_API_KEY`, `APP_SHARED_SECRET`.

---

## 9. Build order

1. **M0 — Schema:** migrations + RLS + storage buckets for PNGs. Seed the 5 subjects.
2. **M1 — Ingestion:** file parsing (PDF text; OCR for photos), question extraction,
   DeepSeek generation, SymPy + cross-model verification, Graphviz dual-render, insert.
   *Blocked on: user's assignment uploads → `/ingestion/samples`.* Build against 2–3
   synthetic questions per subject in the meantime.
3. **M2 — Edge Functions:** `/sync` and `/ask` with shared-secret auth.
4. **M3 — Watch app core:** timer disguise + secret entry + cached nav + answer screen.
5. **M4 — iPhone companion:** full answers + verification queue.
6. **M5 — Live features:** chat tab, value-swap live solve, cache-back.
7. **M6 — Polish:** complication, App Intent, sync UX, Sunday re-sign reminder note in
   SETUP.md.

Definition of done per milestone: runs end-to-end on real device/DB, not just simulator.

---

## 10. v2 backlog (do NOT build now)

- Vision ingestion: photograph a hand-drawn automaton/textbook diagram → model reads it →
  DOT → clean re-render.
- Weak-spot log: record live lookups → weekly digest.
- Practice-sheet generator from value-swap templates (for the brother).
- Health/quick-capture modules on the same backend + app.

## 11. Explicitly rejected (don't resurrect)

- Web app / Vercel frontend on the watch (unreliable renderer, no address bar).
- Raw SVG on watch; hand-placed-coordinate SVG from LLMs anywhere.
- Diffusion image models for diagrams (approximately-right diagrams are wrong).
- Hints-ladder / teaching-mode variants on the watch (user wants answers only).
- Fake "cheap replica watch" OS disguise & side-button remap (watchOS forbids; the
  in-app timer disguise is the sanctioned replacement).

## 12. Open items (ask the user only about these)

1. Assignment files → `/ingestion/samples` (pending upload).
2. ~~40 mm or 44 mm SE 3?~~ **Resolved 2026-07-15: 44 mm** → watch PNG target 368×448
   (render at 2× = 736×896, downscale).
3. ~~Ingestion language preference~~ **Resolved 2026-07-15: Python** (SymPy, Graphviz,
   PDF parsing, and OCR are all Python-native — one language, no subprocess bridge).
4. Confirm DeepSeek prepaid credit is loaded before M1 generation runs.
