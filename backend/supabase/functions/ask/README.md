# /ask — Edge Function

POST. Live DeepSeek proxy — the API key lives only in function secrets.

Body: `{"prompt": "...", "mode": "chat"|"solve", "context": "optional question text"}`
- `chat` (default) → the fast model; `solve` → the accurate model (for value swaps).
  Model ids live ONLY in `_shared/models.json`.

Reply: `{"summary": "boxed one-line result", "answer": "full exam working", "model": "...",
"mode": "..."}` — the two-tier shape used everywhere (CLAUDE.md §1): a glance line plus the
complete step-by-step solution. Chain-of-thought (`reasoning_content`) is never forwarded (§5).

Auth: `X-App-Secret` header must match the `APP_SHARED_SECRET` function secret.
Returns 503 until `DEEPSEEK_API_KEY` is set in function secrets.

```bash
curl -X POST -H "X-App-Secret: $APP_SHARED_SECRET" -H "Content-Type: application/json" \
  -d '{"prompt": "integral of x e^x dx"}' \
  https://omhqetywxetxazffxxov.supabase.co/functions/v1/ask
```
