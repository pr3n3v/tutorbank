Subject: Finite Languages & Automata Theory (FLAT). Diagram-heavy.

- Any DFA/NFA/PDA/Turing machine or grammar-derivation question → emit `diagram_dot`
  (rankdir=LR; doublecircle for accepting states; a start arrow from an invisible node).
- `summary` is a formal one-liner: a regex, a 5-tuple sketch, a grammar, or a verdict
  like "not regular — pumping lemma on aⁿbⁿ". State counts belong in the summary when
  the diagram is the real answer, e.g. "DFA, 4 states — see diagram".
- Use Unicode formal symbols: δ, Σ, ε, ⊢, →, L(M).
- For pumping-lemma and closure proofs: `summary` = the verdict + the witness string;
  the full proof goes in `answer`.
