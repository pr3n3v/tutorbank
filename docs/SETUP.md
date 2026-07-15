# TutorBank — One-Time Setup

## 1. Secrets

```bash
cp .env.example .env   # fill in all four values; .env is gitignored
```

- `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`: Supabase dashboard → Project Settings → API.
  The service-role key is used ONLY by the local ingestion script.
- `DEEPSEEK_API_KEY`: platform.deepseek.com. Keep the account **prepaid-only** — a leaked
  endpoint must not be able to run up unbounded cost.
- `APP_SHARED_SECRET`: generate with `openssl rand -hex 24`. Clients send it as
  `X-App-Secret`; Edge Functions check it against their env.

## 2. Supabase

1. Migrations live in `backend/supabase/migrations/` and are applied via the Supabase
   MCP/CLI. `0001_init.sql` creates the schema, RLS (deny-by-default; only the service
   role can touch tables), the private `diagrams` storage bucket, and seeds the 5
   subjects.
2. Set Edge Function secrets (M2):
   ```bash
   supabase secrets set APP_SHARED_SECRET=... DEEPSEEK_API_KEY=...
   ```

## 3. Ingestion environment (Python)

```bash
cd ingestion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
brew install graphviz         # `dot` must be on PATH for diagram rendering
```

Drop assignment PDFs/photos into `ingestion/samples/` (gitignored).

## 4. Xcode signing (free provisioning)

- Open `app/TutorBank.xcodeproj`, select your personal team under Signing & Capabilities
  for BOTH targets (iOS + watchOS). One bundle ID family, two targets.
- Free provisioning profiles expire every **7 days**.

## 5. ⏰ Weekly re-sign ritual (Sundays)

Every Sunday: plug in the iPhone, open Xcode, build & run the iOS target once (watch app
installs alongside). That re-signs both apps for the next 7 days. If the watch app ever
says it can't launch, this is why.
