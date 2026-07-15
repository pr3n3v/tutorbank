# /ask — Edge Function (M2, not built yet)

Live DeepSeek proxy: `deepseek-v4-flash` by default (chat), `deepseek-v4-pro` for
solve-type value swaps. Holds the DeepSeek key; clients never see it.

Auth: requires `X-App-Secret` header matching the `APP_SHARED_SECRET` function secret.
System prompt enforces one-line replies unless steps are explicitly requested.
See CLAUDE.md §2, §5, §9 M2/M5.
