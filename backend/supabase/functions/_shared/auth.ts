// Shared-secret gate (CLAUDE.md §3): every function requires X-App-Secret matching
// the APP_SHARED_SECRET function secret. Comparison is constant-time via digest.

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export async function requireAppSecret(req: Request): Promise<Response | null> {
  const expected = Deno.env.get("APP_SHARED_SECRET");
  if (!expected) {
    return json({ error: "APP_SHARED_SECRET not configured" }, 500);
  }
  const provided = req.headers.get("x-app-secret") ?? "";
  const enc = new TextEncoder();
  const [a, b] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(provided)),
    crypto.subtle.digest("SHA-256", enc.encode(expected)),
  ]);
  const av = new Uint8Array(a);
  const bv = new Uint8Array(b);
  let diff = 0;
  for (let i = 0; i < av.length; i++) diff |= av[i] ^ bv[i];
  if (diff !== 0) {
    return json({ error: "unauthorized" }, 401);
  }
  return null;
}
