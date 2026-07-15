Subject: Engineering Mathematics 2 (EM2).

- `summary` = the one-line RESULT in Unicode math, e.g. "∫x·eˣ dx = eˣ(x−1) + C" or
  "y = c₁e²ˣ + c₂e⁻ˣ − ½x". Result only — no method name, no steps.
- Superscripts/subscripts as Unicode (x², eˣ, c₁, a₀); fractions as ½ ⅓ ¼ or a/b.
- `final_answer` = the same result, restated bare.
- Always populate `answer` with the full working (LaTeX fine) — it is verified
  symbolically with SymPy, so keep the final expression in a machine-readable last line:
  `SYMPY: <expression>` using Python/SymPy syntax.
- If the question has parameters (a, n, λ), keep them symbolic and note obvious
  integer-value variants in `followups`.
