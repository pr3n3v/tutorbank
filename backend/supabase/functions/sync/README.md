# /sync — Edge Function

GET. Returns the full question bank as JSON (subjects → assignments + units → questions
→ answers) for the watch/phone offline cache. Diagram PNG paths are converted to
short-lived signed URLs (1 h) — clients download them immediately during sync.
`format_profile` (generation config) is never included.

Auth: `X-App-Secret` header must match the `APP_SHARED_SECRET` function secret
(constant-time check; JWT verification is off — the secret is the gate, per CLAUDE.md §3).

```bash
curl -H "X-App-Secret: $APP_SHARED_SECRET" \
  https://omhqetywxetxazffxxov.supabase.co/functions/v1/sync
```
