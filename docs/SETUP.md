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

## 4. Xcode project (generated, not committed)

```bash
brew install xcodegen        # once
cd app
./scripts/gen_secrets.sh     # .env -> Shared/Secrets.swift (gitignored)
xcodegen generate            # project.yml -> TutorBank.xcodeproj
open TutorBank.xcodeproj
```

Re-run `gen_secrets.sh` whenever `.env` changes; re-run `xcodegen generate` whenever
files are added/removed or `project.yml` changes.

## 5. Install on the physical Apple Watch SE 3 (free provisioning)

One-time, then a 7-day re-sign (§6). Automatic signing is pre-enabled in project.yml;
you only pick the team.

**a. Xcode account (once):** Xcode → Settings → Accounts → add your Apple ID (a free
account is fine — no paid Developer Program needed).

**b. Devices (once):**
- Pair the Apple Watch SE 3 with your iPhone (iPhone Watch app) if not already.
- Connect the iPhone to the Mac by USB the first time (wireless works after).
- Enable Developer Mode: iPhone → Settings → Privacy & Security → Developer Mode → on →
  restart. Same on the watch → Settings → Privacy & Security → Developer Mode.

**c. Pick your team:** in Xcode, select the **TutorBank** target → Signing & Capabilities
→ Team = your personal team. Repeat for the **TutorBankWatch** target.
- If it says *"bundle identifier is not available"*, the `com.pr3n3v.*` prefix is taken —
  change `bundleIdPrefix` in `app/project.yml` to something unique (e.g. `com.<you>`),
  re-run `xcodegen generate`, and pick the team again.

**d. Run:** choose your Apple Watch as the run destination (top bar) → Product → Run
(⌘R). First build to a device takes a minute.

**e. Trust the developer (first run only):** on the iPhone (and watch if prompted) →
Settings → General → VPN & Device Management → your Apple ID → Trust. Then re-run.

The app installs on the watch as **"StudyTimer"** (the disguise name). Launch it → the
study timer → long-press the time for ~1.2 s to enter the tutor UI.

## 6. ⏰ Weekly re-sign ritual (Sundays)

Free-provisioning signatures expire every **7 days**. Every Sunday: connect the iPhone,
open the project, Product → Run once. That re-signs both apps for another 7 days. If the
watch app won't launch ("unable to verify"), this expiry is why. Free provisioning also
caps you at **3 sideloaded apps per device**.
