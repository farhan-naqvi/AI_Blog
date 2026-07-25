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

1. Follow [Guided Supabase activation](docs/supabase-setup.md). Apply migrations with the Supabase CLI; do not rerun the initial SQL manually.
2. Copy `.env.example` to `.env` and fill values locally. Create `.env.local` with only the two `NEXT_PUBLIC_SUPABASE_*` values.
3. Install and run the UI:

   ```powershell
   npm install
   npm run dev
   ```

4. Install the Python package:

   ```powershell
   python -m pip install -e ".\backend[test]"
   ```

## Operations

Run one collection pass:

```powershell
signalwatch collect
signalwatch collect --connector github
```

Run the bounded four-connector smoke test (one source and at most three fetched entries per connector):

```powershell
python -m signalwatch.cli smoke-test-collectors
```

Run one bounded connector collection without invoking Ollama:

```powershell
python -m signalwatch.cli collect --connector rss --source-limit 2 --item-limit 10
```

Start Ollama, set `OLLAMA_MODEL` to an exact locally installed tag, verify it, then run the persistent local worker:

```powershell
ollama list
python -m signalwatch.cli check-ollama
python -m signalwatch.cli e2e-verify
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
npx tsc --noEmit
npm run lint
npm run test
npx supabase test db
npm run build
```

All collector tests use fixtures and mocks; they do not depend on live APIs.

## Deployment

- Publish the frontend with Sites and configure only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` there.
- Add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and optional source tokens as GitHub Actions secrets.
- Never place `SUPABASE_SERVICE_ROLE_KEY` in a browser or `NEXT_PUBLIC_*` variable.
- Keep Ollama and `OLLAMA_*` values on the owner machine only.

See [architecture](docs/architecture.md), [deployment](docs/deployment.md), [local worker](docs/local-worker.md), [retention](docs/data-retention.md), and [source policy](docs/source-policy.md).
