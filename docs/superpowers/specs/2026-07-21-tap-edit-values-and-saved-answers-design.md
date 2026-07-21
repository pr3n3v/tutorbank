# TutorBank — Tap-to-Edit Values & Saved Answers

**Date:** 2026-07-21
**Status:** Approved (design), pending implementation plan
**Scope:** Two connected watch/backend/dashboard features.

---

## 1. Overview & Goals

Two features that share one backbone (the live `/ask` DeepSeek path):

- **A — Tap-to-edit values ("Change the numbers"):** let the user re-solve a maths question
  with different values by tapping the numbers/signs in the question, editing each on a
  focused screen, and solving once. Non-destructive: the canonical question is never
  mutated; each edit session produces a saved *branch*.
- **B — Saved Answers:** every DeepSeek answer (Ask-about-this, tap-edit re-solve, and
  free-chat) is auto-persisted and browsable per subject on the watch, and deletable from
  the Mac dashboard.

They connect: a tap-edit re-solve is just an `/ask` call whose result is saved like any
other. One persistence path, two entry points.

Success criteria:
- On any question with detectable numbers, the user can change values via tap → edit →
  solve, with zero per-question setup, and the original question/answer stay untouched.
- Every successful `/ask` result is saved under the right subject (or General) and shows
  in that subject's "Saved Answers" on the watch.
- The user can delete any saved answer from the dashboard; the watch is read-only for them.

Constraint: the physical watch is mid-repair (pending Xcode re-sign, see project memory),
so **implementation is verified on the watchOS simulator** (same font/runtime).

---

## 2. Feature A — Tap-to-Edit Values

### 2.1 User flow (hub-and-spoke)

1. On a question's Answer screen, tap **"Change the numbers"** (replaces the old
   variable-only "Change values"; now shown on ANY question with ≥1 detectable number).
2. The **hub** appears: the question rendered with its numbers and operators as tappable
   **chips**, prose as plain text, and a **"Solve"** button pinned at the bottom.
3. Tap a chip → a **focused edit screen** for that single value (math keypad + Scribble +
   erase). Confirm → return to the hub; the edited chip is **highlighted** to show it
   changed.
4. Repeat for any chips, in any order. Nothing is sent to DeepSeek until step 5.
5. Tap **"Solve"** → the modified question is reconstructed and sent to `/ask` (solve
   mode). The answer renders in the existing live-answer view and is auto-saved as a
   branch (Feature B, `source = tap_edit`).

### 2.2 Tokenizing the question (runtime, no schema change)

- A Swift tokenizer splits `question.text` into an ordered list of **segments**, each
  `fixed` (prose, variable letters, brackets, commas, whitespace) or `editable`.
- **Editable segment types:**
  - `number` — regex `\d+(\.\d+)?`, plus a leading `-` treated as unary sign only when
    preceded by start-of-string, `(`, `=`, or another operator (otherwise the `-` is an
    operator segment). This unary-minus rule is the one real parsing nuance; nail it in the
    plan with unit tests.
  - `operator` — a standalone `+ − × ÷ = / ^` between terms.
- Brackets `( ) [ ]` and commas are **fixed** (they carry structure, e.g. matrices). You
  change brackets *inside* a chip via the keypad, so a 3×3 matrix stays 9 chips, not ~25.
- **Reconstruction** = concatenate segments in order, substituting each editable segment's
  current value. Pure string rebuild; deterministic.

### 2.3 The edit screen

Pushed from the hub for one chip. Contents:
- The chip's **current value** in a Scribble/dictation-enabled field.
- A **math keypad**: `0–9 . ,` · `( ) [ ]` · `/ ^ ±` (± flips sign, ^ starts a power) ·
  operators `+ − × ÷ =`.
- **Erase:** `⌫` backspace (one character) and `C` clear (empties the whole cell, including
  the original starting value, so you can type fresh).
- Confirm returns the new string to the hub, which updates the token model in memory.

### 2.4 Non-destructive branching (hard requirement)

- All edits mutate an **in-memory copy** of the token list. The `questions` row is **never
  written**. Clearing/erasing affects only the copy.
- On **Solve**, the reconstructed (modified) question + its `/ask` answer are saved as a
  **new `saved_answers` branch** (`source = tap_edit`, under the question's subject). One
  question can spawn many independent branches; the canonical question and its
  verified answer are untouched.

### 2.5 Watch components

- `ValueEditHubView(question)` — tokenizes, renders chips via a wrapping flow layout
  (custom SwiftUI `Layout`, since watchOS has no built-in flow), holds edit state, has the
  Solve button. Supersedes `ValueSwapView`.
- `ValueEditKeypadView(current) -> String` — the focused single-cell editor.
- Solve calls `LiveAnswerModel.start(prompt: reconstructedQuestion, mode: .solve,
  context: originalQuestionText, subjectId: subject.id, source: "tap_edit")`.
- The old variable-based path (`question.variables`, 3 questions) is retired; those
  questions now use the same tap-edit UI. The `variables` column may remain unused.

---

## 3. Feature B — Saved Answers

### 3.1 Data model (migration `0003_saved_answers.sql`)

```sql
create table if not exists saved_answers (
  id           uuid primary key default gen_random_uuid(),
  subject_id   uuid references subjects(id) on delete cascade,  -- NULL = General bucket
  question_text text not null,   -- the prompt actually asked (modified question for tap_edit)
  summary      text not null,
  answer       text,
  model        text,
  source       text not null default 'ask',   -- 'ask' | 'tap_edit' | 'chat'
  created_at   timestamptz not null default now()
);
create index if not exists idx_saved_answers_subject
  on saved_answers(subject_id, created_at desc);
-- RLS: deny-by-default, service role only (mirror existing tables in 0001_init.sql).
```

### 3.2 Persistence path (server-side, in `/ask`)

- `/ask` request body gains optional `subject_id` (uuid | null) and `source`
  ('ask' | 'tap_edit' | 'chat', default 'ask').
- After a successful generation, `/ask` inserts one `saved_answers` row via a service-role
  Supabase client (Edge Functions may use `SUPABASE_SERVICE_ROLE_KEY`): `subject_id` from
  the request (NULL for free-chat), `question_text = prompt`, plus summary/answer/model/source.
- **Best-effort:** the insert is wrapped so a save failure logs but never fails the answer
  the user is waiting on. Chosen over a separate client-initiated `/save` call for
  reliability (atomic with generation; no lost saves if the watch drops connection).

### 3.3 Fetch (dedicated lightweight endpoint, keeps `/sync` lean)

- New `saved` Edge Function, `POST /saved { subject_id }` where `subject_id` is a uuid or
  the literal `"general"` (→ `subject_id IS NULL`). Returns
  `[{ id, question_text, summary, answer, model, source, created_at }]`, newest first,
  auth via `X-App-Secret` like the others.
- The watch calls it lazily when the user opens a Saved Answers section — NOT part of the
  bulk `/sync`, so the bank stays small.

### 3.4 Watch UI

- **Subject detail** (below the Units list): a `NavigationLink` **"Saved Answers (N)"** →
  `SavedAnswersListView(subjectId)`. Fetches via `/saved`, lists each entry
  (question_text + summary, newest first); tap → full-answer view reusing the existing
  `SummaryText` + `WorkingView` rendering.
- **Subjects list:** a **"General"** row at the bottom → `SavedAnswersListView(subjectId: nil)`
  for free-chat saves.
- **Read-only on the watch** — no delete affordance (deletion is dashboard-only, §3.5).

### 3.5 Dashboard (Mac) — management

- Backend: `fetch_saved()` (grouped by subject + General with counts); `/api/saved` (list);
  extend `delete_tree` with kind `saved_answer` (`delete from saved_answers where id=…`).
  Add `saved_answers` to the delete allow-list.
- SPA: a **"Saved"** tab listing saved answers grouped by subject / General, each row
  showing question + summary + source badge + a **delete** button (reuses the existing
  confirm-then-`/api/delete` flow). Deleting one never touches the canonical bank.

---

## 4. Endpoints & files touched (summary)

| Area | Change |
|------|--------|
| DB | `backend/supabase/migrations/0003_saved_answers.sql` (new table, index, RLS) |
| Edge fn `ask` | accept `subject_id`+`source`; best-effort insert into `saved_answers` |
| Edge fn `saved` | NEW — `POST /saved {subject_id}` list |
| Watch | `ValueEditHubView`, `ValueEditKeypadView` (replace `ValueSwapView`); `SavedAnswersListView`; "Saved Answers" row in subject view; "General" row in Subjects list; `AskService` gains `subjectId`/`source` params + a `fetchSaved` call |
| Dashboard | `fetch_saved`, `/api/saved`, `delete_tree` kind `saved_answer`, new "Saved" tab in the SPA |

---

## 5. Non-goals (YAGNI)

- No watch-side deletion of saved answers (dashboard only).
- No dedup of repeated asks and no cap on saved count (pruned in the dashboard).
- No full LaTeX/equation editor — the keypad is the fixed set in §2.3.
- No offline editing/queueing; Solve and Save require connectivity.
- The `questions.variables` templating path is retired, not extended.

---

## 6. Risks & mitigations

- **Unary-minus vs operator ambiguity** in the tokenizer → explicit rule (§2.2) + unit
  tests for the common shapes (`4x−2y`, `−2`, `=−3`, `(−1)`).
- **Flow layout on watchOS** (no native wrap) → small custom `Layout`; test with a 3×3
  matrix (9 chips) for wrapping + tap-target size on 44mm.
- **`/ask` now writes to the DB** → best-effort save, never blocks/fails the answer;
  covered by a test that a save error still returns the answer.
- **Scribble reliability for math** → keypad is primary; Scribble is a secondary path.
- **Saved-answers growth** → dashboard-managed; acceptable for a single-user app.

---

## 7. Testing (simulator)

Real watch is pending re-sign, so verify on the SE 3 44mm sim (watchOS 26.5):
- Tokenizer unit tests (Swift) for the parsing shapes above.
- Tap-edit end-to-end: open a matrix question → edit 2–3 chips → Solve → correct modified
  question reaches `/ask` → answer renders → a `tap_edit` row appears in `saved_answers`
  with the modified `question_text`; the canonical question row is unchanged.
- Saved Answers: Ask-about-this and free-chat each produce a row under the right
  subject / General; the watch list shows them; dashboard delete removes one without
  touching the bank.
- Render-safety: edited values respect the ASCII sub/superscript rule (§ watch-font memo).

---

## 8. Decisions log

1. Change-values input = **hub-and-spoke tap-to-edit** (one value per screen, return to
   hub, final Solve). [user]
2. Editable chips = **numbers + operators**; brackets edited inside the keypad, not as
   separate chips. [assistant, user-approved]
3. Detection is **runtime** (Swift regex over `question.text`) — zero setup, no migration
   to `questions`. [assistant]
4. **Non-destructive branching**: edits on an in-memory copy; original never written; branch
   saved on Solve. [user, hard requirement]
5. Saved answers = **auto-save ALL** `/ask` results; subject-context → subject, free-chat →
   **General** (`subject_id NULL`). [user]
6. Persistence = **server-side best-effort insert in `/ask`** (reliability over a separate
   client call). [assistant, matches approved design]
7. Watch fetches saved via a **dedicated `/saved` endpoint**, not `/sync`. [assistant]
8. **No dedup, no cap.** [user-approved]
9. Deletion = **dashboard only**; watch is read-only for saved answers. [user]
