# SignalWatch AI

SignalWatch is an automation-first AI monitoring MVP. GitHub Actions collects public source metadata into Supabase even when the owner computer is offline. A local worker later claims queued items, extracts readable source text in memory, processes it with Ollama, applies deterministic evidence rules, and persists only durable structured intelligence.

No OpenAI API, paid model API, hosted inference, LinkedIn scraping, or X/Twitter scraping is used.

## Components

- Vinext/React/TypeScript public intelligence dashboard and private owner workspace
- Supabase Postgres, Auth, RLS, full-text search, RPC job claiming, and cron cleanup
- Python/FastAPI package with RSS, GitHub, arXiv, and Hugging Face collectors
- Local Ollama structured-output worker
- GitHub Actions cloud collection schedule

The frontend lives at the repository root because the Sites runtime expects that layout. Python code is under `backend/`.

## Local setup

1. Copy `.env.example` to `.env` and fill the Supabase values.
2. Run `supabase/migrations/202607250001_initial_schema.sql`, then `supabase/seed.sql` in Supabase SQL Editor.
3. Enable `pg_cron`, then apply `supabase/migrations/202607250002_cleanup_schedule.sql`.
4. Create one Supabase Auth user, disable public sign-ups, and set the owner:

   ```sql
   update public.private_settings
   set owner_user_id = (select id from auth.users where lower(email) = lower('owner@example.com')),
       owner_email = 'owner@example.com';
   ```

5. Install and run the UI:

   ```powershell
   npm install
   npm run dev
   ```

6. Install the Python package:

   ```powershell
   python -m pip install -e ".\backend[test]"
   ```

## Operations

Run one collection pass:

```powershell
signalwatch collect
signalwatch collect --connector github
```

Start Ollama, ensure the configured model is installed, then run the persistent local worker:

```powershell
ollama pull qwen2.5:7b
signalwatch worker --watch --interval 60
```

The worker generates daily and weekly reports only when enough verified developments exist. Temporary extracted text remains in process memory and is discarded after each job.

Run the optional local FastAPI health surface:

```powershell
uvicorn signalwatch.api:app --host 127.0.0.1 --port 8000
```

## Tests

```powershell
python -m pytest backend -q
npm run build
```

All collector tests use fixtures and mocks; they do not depend on live APIs.

## Deployment

- Publish the frontend with Sites and configure only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` there.
- Add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and optional source tokens as GitHub Actions secrets.
- Never place `SUPABASE_SERVICE_ROLE_KEY` in a browser or `NEXT_PUBLIC_*` variable.
- Keep Ollama and `OLLAMA_*` values on the owner machine only.

See [architecture](docs/architecture.md), [deployment](docs/deployment.md), [local worker](docs/local-worker.md), [retention](docs/data-retention.md), and [source policy](docs/source-policy.md).
