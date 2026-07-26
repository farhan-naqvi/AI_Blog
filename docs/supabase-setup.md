# Guided Supabase activation

The migrations are designed for a new SignalWatch project. The initial migration is not a rerunnable bootstrap script: apply it once through Supabase migration history. Do not paste service keys into chat, terminal output, source files, or frontend variables.

## 1. Create and link the project

1. In the Supabase dashboard, create a project and retain its project reference, API URL, anon/publishable key, and service-role secret privately.
2. Disable public user sign-ups under **Authentication > Providers > Email**. Keep email/password sign-in enabled for the owner.
3. Enable the `pg_cron` extension under **Database > Extensions**.
4. Install the CLI, authenticate, and link this repository:

   ```powershell
   npm install
   npx supabase login
   npx supabase link --project-ref <PROJECT_REF>
   npx supabase migration list
   npx supabase db push --dry-run
   ```

5. Confirm the dry run contains only the three reviewed migrations (`202607250001_initial_schema.sql` through `202607250003_structured_extraction.sql`), then apply them:

   ```powershell
   npx supabase db push
   ```

6. Run `supabase/seed.sql` once in the dashboard SQL Editor. It is idempotent by source name and creates 41 configured sources, of which 21 are active.

Never use `db reset --linked` against this project. If the first migration is partially applied, stop and inspect migration history instead of rerunning the SQL manually.

## Auth URLs for the deployed owner workspace

In Supabase Dashboard, open **Authentication → URL Configuration** and set:

1. **Site URL:** `https://signalwatch-ai.farhannaqvi16.chatgpt.site`
2. **Redirect URLs:** add `https://signalwatch-ai.farhannaqvi16.chatgpt.site/**`
3. Keep local development explicitly allowed with `http://localhost:3000/**` and, when using the alternate local port, `http://localhost:3001/**`.
4. Save the configuration, sign in at `/owner-login`, confirm `/admin` loads, then use **Sign out** and confirm `/admin` redirects back to `/owner-login`.

Do not place the owner password, service-role key, session tokens, or Auth user ID in these URL fields or documentation.

## 2. Verify schema and functions

Run this read-only query in the SQL Editor:

```sql
select tablename, rowsecurity
from pg_tables
where schemaname = 'public'
order by tablename;

select routine_name
from information_schema.routines
where routine_schema = 'public'
  and routine_name in (
    'claim_processing_jobs', 'claim_processing_job_by_id',
    'finalize_processing_job',
    'fail_processing_job', 'cleanup_expired_data',
    'search_public_developments'
  )
order by routine_name;

select connector_key, active, count(*)
from public.sources
group by connector_key, active
order by connector_key, active;

select jobname, schedule, active
from cron.job
where jobname = 'signalwatch-retention-cleanup';
```

All public tables must report `rowsecurity = true`; all six functions and the active cleanup job must be present.

## 3. Create and bind the owner

1. In **Authentication > Users**, create the single owner user with the intended email and a strong password.
2. Run the following block after replacing only the email placeholder:

   ```sql
   do $$
   declare v_owner uuid;
   begin
     select id into v_owner
     from auth.users
     where lower(email) = lower('OWNER_EMAIL_HERE')
     limit 1;

     if v_owner is null then
       raise exception 'Owner Auth user was not found';
     end if;

     update public.private_settings
     set owner_user_id = v_owner,
         owner_email = null,
         updated_at = now();
   end $$;
   ```

Using the immutable Auth user ID avoids email-based authorization. Confirm without exposing the ID:

```sql
select owner_user_id is not null as owner_bound,
       owner_email is null as email_fallback_disabled
from public.private_settings;
```

## 4. Verify RLS before activation

Set the API values only in the current shell, then issue anonymous REST checks. Do not paste their values into the command history if that is unsuitable for your environment.

```powershell
$env:SUPABASE_URL = 'https://PROJECT_REF.supabase.co'
$env:SUPABASE_ANON_KEY = '<ANON_KEY>'
$headers = @{ apikey = $env:SUPABASE_ANON_KEY; Authorization = "Bearer $env:SUPABASE_ANON_KEY" }

Invoke-RestMethod "$env:SUPABASE_URL/rest/v1/developments?select=id,publication_status,verification_status" -Headers $headers
Invoke-RestMethod "$env:SUPABASE_URL/rest/v1/reports?select=id,publication_status" -Headers $headers
Invoke-RestMethod "$env:SUPABASE_URL/rest/v1/sources?select=id,name,reliability_level" -Headers $headers
```

The first two calls may return an empty array, but any rows must be public (`Published`, and developments also `Verified`). The limited source query must succeed. Anonymous requests to each private table must fail with HTTP 401 or 403:

```powershell
foreach ($table in 'linkedin_drafts','processing_jobs','exceptions','operational_logs','private_settings') {
  try { Invoke-WebRequest "$env:SUPABASE_URL/rest/v1/$table?select=*" -Headers $headers -ErrorAction Stop | Out-Null; throw "UNEXPECTED ACCESS: $table" }
  catch { if ($_.Exception.Response.StatusCode.value__ -notin 401,403) { throw } }
}
```

Sign in at `/owner-login`; the bound owner must reach `/admin`. A different authenticated user must be redirected and must receive no private table rows.

After a local Supabase test database is available, run the pgTAP retention and RLS suite:

```powershell
npx supabase test db
```

## 5. Configure environment files

Create `.env.local` at the repository root for the frontend. These are intentionally public browser credentials:

```text
NEXT_PUBLIC_SUPABASE_URL=https://PROJECT_REF.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<ANON_OR_PUBLISHABLE_KEY>
```

Create `.env` at the repository root for collectors and the local worker:

```text
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=<ANON_OR_PUBLISHABLE_KEY>
SUPABASE_SERVICE_ROLE_KEY=<SERVICE_ROLE_SECRET>
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=<INSTALLED_LOCAL_MODEL>
LOCAL_WORKER_ID=<STABLE_OWNER_MACHINE_NAME>
GITHUB_TOKEN=<OPTIONAL_TOKEN>
HUGGINGFACE_TOKEN=<OPTIONAL_TOKEN>
```

Both files are ignored by Git. Only placeholders belong in `.env.example`.

For GitHub Actions, add `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SOURCE_GITHUB_TOKEN` (optional), and `HUGGINGFACE_TOKEN` (optional) as repository secrets. Leave the repository variable `ENABLE_SCHEDULED_COLLECTION` absent or `false` until both controlled checks pass.
