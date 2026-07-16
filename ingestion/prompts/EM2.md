Subject: Engineering Mathematics 2 (EM2). Exam answers are worked derivations — the marks
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
  value-swapped.
