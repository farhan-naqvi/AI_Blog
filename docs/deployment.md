# Deployment

## Supabase

1. Follow [Guided Supabase activation](supabase-setup.md), including the dry run and RLS checks.
2. Create the owner Auth user and bind `private_settings.owner_user_id`; clear the email fallback.
3. Disable public user registration. Use a strong password and MFA if available.
4. Enable `pg_cron` and apply the cleanup schedule migration.
5. Confirm RLS is enabled on every table and the anon role cannot select private tables.

The SQL Editor should report no errors before collector secrets are configured. Keep the service-role key only in GitHub Actions and on the owner computer.

## GitHub Actions

Add repository secrets:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SOURCE_GITHUB_TOKEN` (optional but strongly recommended for rate limits)
- `HUGGINGFACE_TOKEN` (optional)

The workflow supports a manual smoke run and one manually selected connector. Scheduled collection is disabled unless the repository variable `ENABLE_SCHEDULED_COLLECTION` is exactly `true`. When enabled, it runs RSS hourly, GitHub every two hours, Hugging Face every three hours, and arXiv twice daily. Source-level intervals still apply, and overlapping runs are serialized.

First run **Actions > Collect public AI sources > Run workflow > smoke**. Do not enable schedules until this passes and the local one-item end-to-end diagnostic passes.

## Frontend

Configure these public runtime values in Sites:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

They are designed to be public; RLS protects data. Do not configure service-role, Ollama, source-token, or owner password values in frontend variables.

## Verification checklist

- Public pages return only `Published` + `Verified` developments.
- Anonymous REST requests to `linkedin_drafts`, `exceptions`, `processing_jobs`, and `private_settings` fail.
- A non-owner authenticated account cannot read private tables or call the health RPC.
- Two simultaneous claim calls receive different jobs.
- An unpinned draft disappears after 48 hours; a pinned draft remains.
- Stopping Ollama leaves queued jobs intact while scheduled collection continues.
