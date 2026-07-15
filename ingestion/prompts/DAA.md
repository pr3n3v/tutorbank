Subject: Design & Analysis of Algorithms (DAA).

- Complexity questions → `summary` = the tight bound + one-word reason,
  e.g. "O(n log n) — divide & conquer, T(n)=2T(n/2)+O(n)".
- Recurrences → `summary` = the closed form / Θ-bound, e.g. "T(n) = Θ(n²) — Master case 3".
- "Which algorithm / design an algorithm" → `summary` = algorithm name + one-line core
  idea, e.g. "Kruskal — sort edges, union-find, add if no cycle".
- Trace/table questions (DP tables, Dijkstra steps) → `summary` = the final value/row;
  the table itself goes in `answer`.
- Graph questions may emit `diagram_dot` when a small graph IS the answer.
- Use O/Θ/Ω symbols directly in Unicode.
