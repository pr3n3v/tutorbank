# /sync — Edge Function (M2, not built yet)

Returns the full question bank as JSON (subjects → units → questions → answers, plus
signed URLs for watch PNGs) for the watch/phone offline cache.

Auth: requires `X-App-Secret` header matching the `APP_SHARED_SECRET` function secret.
See CLAUDE.md §2, §3 (security), §9 M2.
