// LaTeX → Unicode cleanup for watch display (§7a: no LaTeX engine on watchOS).
// DeepSeek often emits \boxed{}, \cos, \frac, ^2 etc. even when told not to.

const SYMBOLS: Record<string, string> = {
  "\\cdot": "·", "\\times": "×", "\\div": "÷", "\\pm": "±", "\\mp": "∓",
  "\\leq": "≤", "\\le": "≤", "\\geq": "≥", "\\ge": "≥", "\\neq": "≠", "\\ne": "≠",
  "\\approx": "≈", "\\equiv": "≡", "\\to": "→", "\\rightarrow": "→", "\\Rightarrow": "⇒",
  "\\infty": "∞", "\\int": "∫", "\\sum": "Σ", "\\prod": "∏", "\\sqrt": "√",
  "\\partial": "∂", "\\nabla": "∇", "\\in": "∈", "\\notin": "∉", "\\forall": "∀",
  "\\exists": "∃", "\\Rightarrow ": "⇒", "\\implies": "⇒", "\\land": "∧", "\\lor": "∨",
  "\\alpha": "α", "\\beta": "β", "\\gamma": "γ", "\\delta": "δ", "\\epsilon": "ε",
  "\\theta": "θ", "\\lambda": "λ", "\\mu": "μ", "\\pi": "π", "\\rho": "ρ",
  "\\sigma": "σ", "\\tau": "τ", "\\phi": "φ", "\\omega": "ω",
  "\\Delta": "Δ", "\\Sigma": "Σ", "\\Omega": "Ω", "\\Theta": "Θ", "\\Phi": "Φ",
};

const SUP: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
  "7": "⁷", "8": "⁸", "9": "⁹", "n": "ⁿ", "x": "ˣ", "+": "⁺", "-": "⁻", "i": "ⁱ",
};
const SUB: Record<string, string> = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅",
  "6": "₆", "7": "₇", "8": "₈", "9": "₉", "n": "ₙ", "i": "ᵢ", "j": "ⱼ",
};

function convert(s: string): string {
  let t = s;
  t = t.replace(/\$\$?/g, ""); // strip $ / $$ math delimiters
  // wrappers: \boxed{x} \text{x} \mathrm{x} \mathbf{x} \operatorname{x} -> x
  t = t.replace(/\\(?:boxed|text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}/g, "$1");
  t = t.replace(/\\left|\\right/g, "");
  // \frac{a}{b} -> (a)/(b), one level
  t = t.replace(/\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, "($1)/($2)");
  for (const [k, v] of Object.entries(SYMBOLS)) t = t.split(k).join(v);
  // ^2 ^{2} superscripts, _1 _{1} subscripts (common char sets only)
  t = t.replace(/\^\{?([0-9nxi+\-]+)\}?/g, (_, g: string) => [...g].map((c) => SUP[c] ?? `^${c}`).join(""));
  t = t.replace(/_\{?([0-9nij]+)\}?/g, (_, g: string) => [...g].map((c) => SUB[c] ?? `_${c}`).join(""));
  // strip backslash before remaining word commands (\cos -> cos, \sin -> sin)
  t = t.replace(/\\([a-zA-Z]+)/g, "$1");
  // NB: do NOT blanket-strip { } — braces are legitimate content in FLAT/DAA
  // (set notation {q0,q1}, grammars {S→aSb}). The \boxed/\text/\frac braces were
  // already consumed above. (Mirrors ingestion/dashboard.py _convert.)
  return t;
}

/** Clean the one-line summary (never contains code). */
export function unicodeSummary(s: string): string {
  return convert(s).replace(/\s+/g, " ").trim();
}

/** Clean prose in an answer but leave ```-fenced code blocks untouched
 *  (converting there would mangle escapes like \n in Java). */
export function unicodeAnswer(s: string): string {
  return s
    .split("```")
    .map((part, i) => (i % 2 === 1 ? part : convert(part)))
    .join("```");
}
