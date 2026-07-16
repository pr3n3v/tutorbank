-- Two-tier answer amendment (CLAUDE.md §1/§5): `answer` is now the full exam-scoring
-- worked solution, `summary` the boxed glance line. Re-sync subjects.format_profile with
-- the rewritten ingestion/prompts/<CODE>.md (the DB copy is what generation reads).

update subjects set format_profile = jsonb_build_object('prompt', $flat$Subject: Finite Languages & Automata Theory (FLAT). Diagram-heavy.

`answer` (full exam-scoring solution):
- **Construct DFA/NFA/PDA/TM:** give the formal definition — the 5-tuple (Q, Σ, δ, q₀, F),
  the transition function δ in full (a transition table is ideal), and a one-line note on
  the accepting idea. Emit `diagram_dot` for the machine (rankdir=LR; doublecircle for
  accepting states; a start arrow from an invisible node).
- **Regular expression / grammar:** give the expression/grammar, then justify it covers the
  language (and nothing more) — the reasoning an exam wants.
- **Pumping-lemma / non-regularity proofs:** the FULL proof — assume regular, take pumping
  length p, choose the witness string, pump, derive the contradiction, conclude.
- **Conversions (NFA→DFA, ε-NFA, minimization):** show the subset-construction / step table
  to the final machine.

`summary` (glance line) = the formal one-liner: a regex, a 5-tuple sketch, a grammar, or a
verdict like "not regular — pumping lemma, s = aᵖbᵖ". When a diagram is the real answer,
summary carries the key fact, e.g. "DFA, 4 states — accepts strings ending in 01".

Unicode formal symbols: δ, Σ, ε, ⊢, →, ∈, L(M). Never ASCII-art an automaton.$flat$) where code = 'FLAT';

update subjects set format_profile = jsonb_build_object('prompt', $java$Subject: Programming in Java.

`answer` (full exam-scoring solution) by qtype:
- **`program` (write a program):** the COMPLETE compilable program is the exam answer —
  imports, class, `main` (or the required methods), correct logic. This full code goes in
  `answer` (monospaced) and is shown on the watch as a scrollable code block and full on
  the phone. Add a one-line note on the key idea if it aids marks.
- **`predict_output`:** the exact output, plus a brief why (which lines produce it, any
  trick — autoboxing, integer division, operator precedence, reference vs value).
- **`concept`:** the full examiner-ready explanation — definition, distinction, and a short
  example where it earns marks (e.g. ArrayList vs LinkedList with the complexity of each op).

`summary` (glance line):
- `program` → the ONE key line/idea (e.g. "c[i][j] += a[i][k]*b[k][j] — triple loop"). The
  summary is NEVER the whole program (it can't glance); the program lives complete in `answer`.
- `predict_output` → the exact output, one line (join multi-line output with " ⏎ ").
- `concept` → the one-line definition/distinction.

Code in `answer` must compile as-is.$java$) where code = 'JAVA';

update subjects set format_profile = jsonb_build_object('prompt', $ajava$Subject: Advanced Programming in Java (AJAVA). Same two-tier rules as JAVA, advanced topics.

`answer` (full exam-scoring solution) by qtype:
- **`program`:** the COMPLETE compilable program is the exam answer (imports, class, methods)
  — shown on the watch as a scrollable code block, full on the phone. Cover the advanced
  mechanism correctly: collections, generics, threads/synchronization, JDBC, servlets/JSP,
  streams, lambdas.
- **`predict_output`:** exact output + the reason (thread interleaving, stream laziness,
  generic erasure, exception flow).
- **`concept`:** full examiner-ready explanation with a short illustrative example.

`summary` (glance line):
- `program` → the ONE key line/mechanism (e.g. "synchronized(this) on shared counter — else
  race"); never the whole program.
- `predict_output` → exact output, one line (" ⏎ " joins lines).
- `concept` → one-line definition/distinction naming the exact API/mechanism.

Code in `answer` must compile as-is.$ajava$) where code = 'AJAVA';

update subjects set format_profile = jsonb_build_object('prompt', $em2$Subject: Engineering Mathematics 2 (EM2). Exam answers are worked derivations — the marks
are in the steps, so `answer` must be a COMPLETE solution, not just the result.

`answer` (full exam-scoring solution) MUST include, in order:
- The method named up front (e.g. "Integration by parts", "Auxiliary equation method",
  "Laplace transform", "Variation of parameters", "Cauchy–Euler").
- Every step written out as on paper, one idea per line, Unicode math:
  - state the formula/rule used (e.g. ∫u dv = uv − ∫v du);
  - the substitutions/choices (e.g. u = x, dv = eˣdx ⟹ du = dx, v = eˣ);
  - each transformation with its intermediate result;
  - simplification to the final form.
- The final answer boxed on its own last line (e.g. "∴ ∫x·eˣ dx = eˣ(x−1) + C").
- A machine-checkable last line for SymPy verification:
  `SYMPY: <final expression in Python/SymPy syntax>` (e.g. `SYMPY: exp(x)*(x-1)`).
  For ODEs give the general solution; for definite integrals give the numeric/exact value.

Worked example — question "∫x·eˣ dx":
  summary: "∫x·eˣ dx = eˣ(x−1) + C"
  answer:
    "Method: integration by parts, ∫u dv = uv − ∫v du.
     Let u = x  ⟹ du = dx;  dv = eˣ dx ⟹ v = eˣ.
     ∫x·eˣ dx = x·eˣ − ∫eˣ dx
              = x·eˣ − eˣ + C
              = eˣ(x − 1) + C.
     ∴ ∫x·eˣ dx = eˣ(x − 1) + C
     SYMPY: exp(x)*(x-1)"

Formatting:
- `summary` = the boxed final RESULT only, Unicode (superscripts x², eˣ; subscripts c₁, a₀;
  fractions ½ ⅓ or a/b). No method name, no steps in `summary`.
- Keep parameters symbolic when the question has them (a, n, λ); note obvious
  integer-value variants in `followups`, and populate `variables` upstream so they can be
  value-swapped.$em2$) where code = 'EM2';

update subjects set format_profile = jsonb_build_object('prompt', $daa$Subject: Design & Analysis of Algorithms (DAA).

`answer` (full exam-scoring solution) depends on the question type:
- **Complexity / recurrence:** show the full derivation — set up the recurrence, name the
  method (Master theorem case, recursion tree, substitution), do the steps, reach the bound.
  Don't just assert Θ(n log n); derive it.
- **"Design an algorithm":** give the approach, the pseudocode (numbered steps or clean
  monospace), a correctness argument, and the complexity analysis — the full exam answer.
- **Trace questions (DP table, Dijkstra, Kruskal):** show the table/steps row by row to the
  final state. Large tables → also emit a PNG per §6; keep a readable text trace in `answer`.
- **Proofs (greedy-choice, optimal substructure):** the complete argument.

`summary` (glance line) = the exam-decisive result, NOT a method walk-through:
- Complexity → the bound + ≤4-word reason: "O(n log n) — divide & conquer".
- Recurrence → the closed form: "T(n) = Θ(n²) — Master case 3".
- "Design an algorithm" → algorithm name + complexity: "MST — Kruskal, O(E log E)".
  (The sort/union-find steps belong in `answer`, not the glance line.)
- DP trace → the final cell/value, e.g. "LCS = 4".

Use O / Θ / Ω in Unicode. Graph questions may emit `diagram_dot` when a small graph is the
answer.$daa$) where code = 'DAA';
