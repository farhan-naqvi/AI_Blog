# Deployment

## Supabase

1. Create a project and apply the initial migration and seed.
2. Create the owner Auth user and set `private_settings.owner_user_id` and `owner_email`.
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

The workflow runs RSS hourly, GitHub every two hours, Hugging Face every three hours, and arXiv twice daily. Source-level intervals still apply, and overlapping runs are serialized.

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
