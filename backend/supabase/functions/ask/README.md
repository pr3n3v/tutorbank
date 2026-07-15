# /ask — Edge Function

POST. Live DeepSeek proxy — the API key lives only in function secrets.

Body: `{"prompt": "...", "mode": "chat"|"solve", "context": "optional question text"}`
- `chat` (default) → the fast model; `solve` → the accurate model (for value swaps).
  Model ids live ONLY in `_shared/models.json`.

Reply: `{"reply": "one line", "model": "...", "mode": "..."}` — the system prompt
enforces one-line answers unless steps are explicitly requested; chain-of-thought
(`reasoning_content`) is never forwarded (CLAUDE.md §5).

Auth: `X-App-Secret` header must match the `APP_SHARED_SECRET` function secret.
Returns 503 until `DEEPSEEK_API_KEY` is set in function secrets.

```bash
curl -X POST -H "X-App-Secret: $APP_SHARED_SECRET" -H "Content-Type: application/json" \
  -d '{"prompt": "integral of x e^x dx"}' \
  https://omhqetywxetxazffxxov.supabase.co/functions/v1/ask
```
