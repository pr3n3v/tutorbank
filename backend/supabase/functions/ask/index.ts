// /ask — live DeepSeek proxy (CLAUDE.md §2, §5, §9 M2). POST, auth via X-App-Secret.
// Body: { "prompt": string, "mode"?: "chat" | "solve", "context"?: string }
//   chat  (default) -> fast model; solve -> accurate model (ids: _shared/models.json)
// Reply is ONE line unless the prompt explicitly asks for steps.

import { json, requireAppSecret } from "../_shared/auth.ts";
import {
  ASK_MAX_PROMPT_CHARS,
  ASK_TIMEOUT_MS,
  DEEPSEEK_BASE_URL,
  MODEL_LIVE,
  MODEL_SOLVE,
} from "../_shared/config.ts";

const SYSTEM_PROMPT = [
  "You are an expert tutor answering on a tiny watch screen.",
  "Reply with EXACTLY ONE line: the direct, exam-ready answer. No preamble,",
  'no "we get", no explanation, no markdown.',
  "Math in Unicode (∫ ² √ δ → λ Σ), never LaTeX.",
  "Only if the user explicitly asks for steps may you use multiple short lines.",
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
      body: JSON.stringify({ model, messages, stream: false }),
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
  const reply: string = completion?.choices?.[0]?.message?.content?.trim() ?? "";
  if (!reply) return json({ error: "empty model reply" }, 502);

  return json({ reply, model, mode });
});
