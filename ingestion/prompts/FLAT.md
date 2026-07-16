Subject: Finite Languages & Automata Theory (FLAT). Diagram-heavy.

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

Unicode formal symbols: δ, Σ, ε, ⊢, →, ∈, L(M). Never ASCII-art an automaton.
