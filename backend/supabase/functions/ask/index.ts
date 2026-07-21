// /ask — live DeepSeek proxy (CLAUDE.md §2, §5, §7, §9 M2). POST, auth via X-App-Secret.
// Body: { "prompt": string, "mode"?: "chat" | "solve", "context"?: string }
//   chat  (default) -> fast model; solve -> accurate model (ids: _shared/models.json)
// Returns the two-tier answer shape used everywhere: { summary, answer } — a boxed
// one-line result plus the full exam-ready working (§1 prime directive).

import { json, requireAppSecret } from "../_shared/auth.ts";
import {
  ASK_MAX_PROMPT_CHARS,
  ASK_TIMEOUT_MS,
  DEEPSEEK_BASE_URL,
  MODEL_LIVE,
  MODEL_SOLVE,
} from "../_shared/config.ts";
import { unicodeAnswer, unicodeSummary } from "../_shared/mathtext.ts";

/** Extract {summary, answer} from a model reply that may be fenced or slightly
 *  malformed JSON. Tries strict parse, then lenient per-field regex. */
function parseTwoTier(content: string): { summary: string; answer: string } {
  // Strip a wrapping ```json ... ``` fence if present.
  let c = content.trim();
  const fence = c.match(/^```(?:json)?\s*\n?([\s\S]*?)\n?```$/);
  if (fence) c = fence[1].trim();

  try {
    const p = JSON.parse(c);
    if (p && typeof p === "object") {
      return {
        summary: typeof p.summary === "string" ? p.summary.trim() : "",
        answer: typeof p.answer === "string" ? p.answer.trim() : "",
      };
    }
  } catch {
    // fall through to lenient extraction
  }

  const field = (name: string): string => {
    // Capture the quoted value, tolerating escaped quotes and raw newlines.
    const m = c.match(new RegExp(`"${name}"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"`));
    if (!m) return "";
    try {
      return (JSON.parse(`"${m[1]}"`) as string).trim(); // unescape \n, \" etc.
    } catch {
      return m[1].trim();
    }
  };
  const summary = field("summary");
  const answer = field("answer");
  // Nothing parseable at all → treat the raw reply as the working.
  return summary || answer ? { summary, answer } : { summary: "", answer: c };
}

const SYSTEM_PROMPT = [
  "You are an expert tutor. The student must reproduce your answer in an exam and score",
  "full marks, so give the COMPLETE worked solution — every step, method named, final",
  "answer boxed. Engineering answers are long; the marks are in the working.",
  "Respond with strict JSON only (no markdown fences):",
  '{"summary": "...", "answer": "..."} where',
  "`summary` is ONE line — the final answer only, no steps; and `answer` is the full",
  "step-by-step exam solution, one idea per line. summary must match answer's result.",
  "CRITICAL — the display has NO LaTeX renderer. Use plain UNICODE math only:",
  "write cos(2x) NOT \\cos(2x), x² NOT x^2, √ ∫ Σ ≤ → π δ as Unicode characters,",
  "a/b for fractions. NEVER emit backslash commands (\\boxed, \\frac, \\cos) or $…$.",
  "Digit sub/superscripts are fine (x², x₁, A⁻¹), but write LETTER indices/exponents as",
  "ASCII — a_ij not aᵢⱼ, A^T not Aᵀ, a^n, v_n, a_(n+1) — the watch font lacks glyphs like",
  "subscript-j so they'd show as ☐.",
  "Wrap code, pseudocode, program output, and any column-aligned block (tables,",
  "derivations) in ```language fenced blocks so the watch keeps them monospaced; keep",
  "ordinary prose OUTSIDE the fences. Inside a fence, put ONE statement per line and",
  "NEVER prefix lines with your own line/step numbers (no '1.', '2.', 'L1:') — the watch",
  "draws its own line-number gutter, so manual numbers would appear twice.",
  "Never include chain-of-thought or 'thinking' meta-commentary; `answer` is the clean",
  "solution a student writes, not a reasoning log.",
].join(" ");

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405);
  const denied = await requireAppSecret(req);
  if (denied) return denied;

  const apiKey = Deno.env.get("DEEPSEEK_API_KEY");
  if (!apiKey) return json({ error: "DEEPSEEK_API_KEY not configured" }, 503);

  let body: { prompt?: unknown; mode?: unknown; context?: unknown };
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON body" }, 400);
  }

  const prompt = typeof body.prompt === "string" ? body.prompt.trim() : "";
  if (!prompt) return json({ error: "prompt required" }, 400);
  if (prompt.length > ASK_MAX_PROMPT_CHARS) {
    return json({ error: `prompt too long (max ${ASK_MAX_PROMPT_CHARS})` }, 400);
  }
  const mode = body.mode === "solve" ? "solve" : "chat";
  const model = mode === "solve" ? MODEL_SOLVE : MODEL_LIVE;
  const context = typeof body.context === "string" && body.context.trim()
    ? body.context.trim()
    : null;
  // context shares the size budget — it is client input hitting the same paid model.
  if (context && context.length + prompt.length > ASK_MAX_PROMPT_CHARS) {
    return json({ error: `prompt+context too long (max ${ASK_MAX_PROMPT_CHARS})` }, 400);
  }

  const messages = [
    { role: "system", content: SYSTEM_PROMPT },
    ...(context ? [{ role: "system", content: `Question context:\n${context}` }] : []),
    { role: "user", content: prompt },
  ];

  let upstream: Response;
  try {
    upstream = await fetch(`${DEEPSEEK_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages,
        stream: false,
        response_format: { type: "json_object" },
      }),
      signal: AbortSignal.timeout(ASK_TIMEOUT_MS),
    });
  } catch (e) {
    const timedOut = e instanceof DOMException && e.name === "TimeoutError";
    return json({ error: timedOut ? "model timeout" : "upstream unreachable" }, 504);
  }

  if (!upstream.ok) {
    // Never forward upstream bodies verbatim — they can carry account details.
    return json({ error: `deepseek error (status ${upstream.status})` }, 502);
  }

  // The timeout signal also governs body reads; a mid-read abort or truncated
  // body must map to the JSON error contract, not an uncaught 500.
  let completion: { choices?: { message?: { content?: string } }[] };
  try {
    completion = await upstream.json();
  } catch (e) {
    const timedOut = e instanceof DOMException && e.name === "TimeoutError";
    return json({ error: timedOut ? "model timeout" : "malformed model response" }, timedOut ? 504 : 502);
  }
  // .content only — reasoning_content (chain-of-thought) is never returned (§5).
  const content: string = completion?.choices?.[0]?.message?.content?.trim() ?? "";
  if (!content) return json({ error: "empty model reply" }, 502);

  // Model was asked for {summary, answer} JSON, but flash sometimes wraps it in
  // ```json fences or emits raw newlines inside strings (invalid JSON). Parse
  // robustly: strip fences, try JSON.parse, then fall back to lenient field extraction.
  const { summary: rawSummary, answer: rawAnswer } = parseTwoTier(content);
  let summary = rawSummary;
  let answer = rawAnswer;
  if (!summary && !answer) return json({ error: "empty model reply" }, 502);
  // Belt-and-suspenders: convert any LaTeX the model still emitted to Unicode,
  // leaving fenced code untouched (§7a). Prompt asks for Unicode; this enforces it.
  answer = unicodeAnswer(answer);
  // Backfill an empty summary from the answer's first real line — skip a leading
  // ``` fence so the glance line isn't just a code marker (mirrors dashboard.py).
  summary = summary
    ? unicodeSummary(summary)
    : (answer.split("\n").find((l) => l.trim() && !l.trim().startsWith("```")) ?? "")
      .slice(0, 200);

  return json({ summary, answer, model, mode });
});
