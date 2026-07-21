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

// DIGIT/sign super/subscripts render on the watchOS font; LETTER ones (esp. ⱼ U+2C7C, ᵢ)
// are missing and show as ☐/?, so a script containing a letter falls back to ASCII ^n / _ij
// (see script()). Keeps x², x₁, A⁻¹ pretty. (Mirrors ingestion/dashboard.py.)
const SUP: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶",
  "7": "⁷", "8": "⁸", "9": "⁹", "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
};
const SUB: Record<string, string> = {
  "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄", "5": "₅", "6": "₆",
  "7": "₇", "8": "₈", "9": "₉", "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
};

// Digit/sign run → Unicode super/subscripts; anything with a letter → ASCII (a^n, a_ij),
// parenthesised when it holds a +/-/= so a_(n+1) stays clear.
function script(g: string, uni: Record<string, string>, lead: string): string {
  if ([...g].every((c) => c in uni)) return [...g].map((c) => uni[c]).join("");
  return lead + (/[+\-=]/.test(g) && g.length > 1 ? `(${g})` : g);
}

function convert(s: string): string {
  let t = s;
  t = t.replace(/\$\$?/g, ""); // strip $ / $$ math delimiters
  // wrappers: \boxed{x} \text{x} \mathrm{x} \mathbf{x} \operatorname{x} -> x
  t = t.replace(/\\(?:boxed|text|mathrm|mathbf|mathit|operatorname)\s*\{([^{}]*)\}/g, "$1");
  t = t.replace(/\\left|\\right/g, "");
  // \frac{a}{b} -> (a)/(b), one level
  t = t.replace(/\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}/g, "($1)/($2)");
  for (const [k, v] of Object.entries(SYMBOLS)) t = t.split(k).join(v);
  // Braced group first, then a bare digit/sign run or a single bare letter.
  t = t.replace(/\^\{([^{}]+)\}/g, (_, g: string) => script(g, SUP, "^"));
  t = t.replace(/_\{([^{}]+)\}/g, (_, g: string) => script(g, SUB, "_"));
  t = t.replace(/\^([0-9+\-]+|[A-Za-z])/g, (_, g: string) => script(g, SUP, "^"));
  t = t.replace(/_([0-9+\-]+|[A-Za-z])/g, (_, g: string) => script(g, SUB, "_"));
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
