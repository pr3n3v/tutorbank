-- TutorBank M0: schema + RLS + storage bucket + subject seed (CLAUDE.md §3, §4, §9)
-- Locked names: subjects, assignments, units, questions, answers. Columns may be added,
-- never renamed.

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

create table if not exists subjects (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  code           text not null unique,
  format_profile jsonb
);

create table if not exists assignments (
  id          uuid primary key default gen_random_uuid(),
  subject_id  uuid not null references subjects(id) on delete cascade,
  title       text not null,
  number      int,
  source_file text
);

create table if not exists units (
  id         uuid primary key default gen_random_uuid(),
  subject_id uuid not null references subjects(id) on delete cascade,
  name       text not null,
  position   int not null default 0
);

create table if not exists questions (
  id            uuid primary key default gen_random_uuid(),
  unit_id       uuid references units(id) on delete set null,
  assignment_id uuid references assignments(id) on delete set null,
  text          text not null,
  qtype         text not null check (qtype in
                  ('concept','solve','proof','diagram','predict_output','program')),
  variables     jsonb,
  position      int not null default 0
);

create table if not exists answers (
  id                uuid primary key default gen_random_uuid(),
  question_id       uuid not null references questions(id) on delete cascade,
  variant           text not null default 'default',
  summary           text not null,
  answer            text,
  final_answer      text,
  diagram_dot       text,
  diagram_png_watch text,
  diagram_png_phone text,
  followups         jsonb,
  model_used        text,
  confidence        numeric check (confidence >= 0 and confidence <= 1),
  verified          boolean not null default false,
  created_at        timestamptz not null default now(),
  unique (question_id, variant)
);

create index if not exists idx_assignments_subject on assignments(subject_id);
create index if not exists idx_units_subject       on units(subject_id);
create index if not exists idx_questions_unit      on questions(unit_id);
create index if not exists idx_questions_assignment on questions(assignment_id);
create index if not exists idx_answers_question    on answers(question_id);

-- ---------------------------------------------------------------------------
-- Security: RLS deny-by-default; clients only ever talk to Edge Functions,
-- which use the service role (bypasses RLS). Anon/authenticated get nothing.
-- ---------------------------------------------------------------------------

alter table subjects    enable row level security;
alter table assignments enable row level security;
alter table units       enable row level security;
alter table questions   enable row level security;
alter table answers     enable row level security;

revoke all on subjects, assignments, units, questions, answers
  from anon, authenticated;

-- ---------------------------------------------------------------------------
-- Storage: private bucket for diagram PNGs.
-- Paths: watch/<answer_id>.png (368x448 target) and phone/<answer_id>.png.
-- No storage.objects policies -> only service role can read/write.
-- ---------------------------------------------------------------------------

insert into storage.buckets (id, name, public)
values ('diagrams', 'diagrams', false)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- Seed: the 5 subjects with per-subject prompt fragments (format_profile).
-- Same text lives in ingestion/prompts/<CODE>.md; DB copy is what generation uses.
-- ---------------------------------------------------------------------------

insert into subjects (code, name, format_profile) values
(
  'FLAT',
  'Finite Languages & Automata Theory',
  jsonb_build_object('prompt', $flat$Subject: Finite Languages & Automata Theory (FLAT). Diagram-heavy.

- Any DFA/NFA/PDA/Turing machine or grammar-derivation question → emit `diagram_dot`
  (rankdir=LR; doublecircle for accepting states; a start arrow from an invisible node).
- `summary` is a formal one-liner: a regex, a 5-tuple sketch, a grammar, or a verdict
  like "not regular — pumping lemma on aⁿbⁿ". State counts belong in the summary when
  the diagram is the real answer, e.g. "DFA, 4 states — see diagram".
- Use Unicode formal symbols: δ, Σ, ε, ⊢, →, L(M).
- For pumping-lemma and closure proofs: `summary` = the verdict + the witness string;
  the full proof goes in `answer`.$flat$)
),
(
  'JAVA',
  'Programming in Java',
  jsonb_build_object('prompt', $java$Subject: Programming in Java.

Split by qtype (locked):
- `predict_output` → `summary` = the EXACT program output, one line (join multi-line
  output with " ⏎ "). Nothing else — no "the output is".
- `program` → `summary` = the ONE key line or core idea, e.g.
  "c[i][j] += a[i][k]*b[k][j] — triple loop". Full runnable code goes in `answer` only.
  NEVER attempt full code in `summary`.
- `concept` → `summary` = the one-line definition/distinction an examiner wants,
  e.g. "ArrayList: resizable array, O(1) get; LinkedList: doubly-linked, O(1) insert".
- Code in `answer` must compile as-is: imports, class, main where relevant.$java$)
),
(
  'AJAVA',
  'Advanced Programming in Java',
  jsonb_build_object('prompt', $ajava$Subject: Advanced Programming in Java (AJAVA). Same rules as JAVA:

- `predict_output` → `summary` = exact output, one line (" ⏎ " joins lines).
- `program` → `summary` = the ONE key line/idea; full code in `answer` only.
- `concept` → one-line examiner-ready definition/distinction.
- Code in `answer` must compile as-is.
- Advanced topics (collections, threads, JDBC, servlets, streams): the `summary` names
  the exact API/mechanism, e.g. "synchronized(this) on shared counter — else race".$ajava$)
),
(
  'EM2',
  'Engineering Mathematics 2',
  jsonb_build_object('prompt', $em2$Subject: Engineering Mathematics 2 (EM2).

- `summary` = the one-line RESULT in Unicode math, e.g. "∫x·eˣ dx = eˣ(x−1) + C" or
  "y = c₁e²ˣ + c₂e⁻ˣ − ½x". Result only — no method name, no steps.
- Superscripts/subscripts as Unicode (x², eˣ, c₁, a₀); fractions as ½ ⅓ ¼ or a/b.
- `final_answer` = the same result, restated bare.
- Always populate `answer` with the full working (LaTeX fine) — it is verified
  symbolically with SymPy, so keep the final expression in a machine-readable last line:
  `SYMPY: <expression>` using Python/SymPy syntax.
- If the question has parameters (a, n, λ), keep them symbolic and note obvious
  integer-value variants in `followups`.$em2$)
),
(
  'DAA',
  'Design & Analysis of Algorithms',
  jsonb_build_object('prompt', $daa$Subject: Design & Analysis of Algorithms (DAA).

- Complexity questions → `summary` = the tight bound + one-word reason,
  e.g. "O(n log n) — divide & conquer, T(n)=2T(n/2)+O(n)".
- Recurrences → `summary` = the closed form / Θ-bound, e.g. "T(n) = Θ(n²) — Master case 3".
- "Which algorithm / design an algorithm" → `summary` = algorithm name + one-line core
  idea, e.g. "Kruskal — sort edges, union-find, add if no cycle".
- Trace/table questions (DP tables, Dijkstra steps) → `summary` = the final value/row;
  the table itself goes in `answer`.
- Graph questions may emit `diagram_dot` when a small graph IS the answer.
- Use O/Θ/Ω symbols directly in Unicode.$daa$)
)
on conflict (code) do nothing;
