Subject: Design & Analysis of Algorithms (DAA).

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
answer.
