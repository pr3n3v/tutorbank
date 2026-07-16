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

const SYSTEM_PROMPT = [
  "You are an expert tutor. The student must reproduce your answer in an exam and score",
  "full marks, so give the COMPLETE worked solution — every step, method named, final",
  "answer boxed. Engineering answers are long; the marks are in the working.",
  "Respond with strict JSON only (no markdown fences):",
  '{"summary": "...", "answer": "..."} where',
  "`summary` is ONE line — the boxed final answer only, Unicode math (∫ ² √ δ → λ Σ),",
  "no steps; and `answer` is the full step-by-step exam solution, Unicode-legible,",
  "one idea per line, code in a monospaced block. summary must match answer's result.",
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

  // Model was told to return {summary, answer} as strict JSON (response_format enforces
  // valid JSON). Parse into the two-tier shape; degrade gracefully if a field is missing.
  let summary = "";
  let answer = "";
  try {
    const parsed = JSON.parse(content);
    if (parsed && typeof parsed === "object") {
      summary = typeof parsed.summary === "string" ? parsed.summary.trim() : "";
      answer = typeof parsed.answer === "string" ? parsed.answer.trim() : "";
    } else {
      // Valid JSON but not an object (bare string/number) — treat as the working.
      answer = content;
    }
  } catch {
    // Should not happen under json_object mode; treat the whole reply as the working.
    answer = content;
  }
  if (!summary && !answer) return json({ error: "empty model reply" }, 502);
  if (!summary) summary = answer.split("\n")[0].slice(0, 200);

  return json({ summary, answer, model, mode });
});
