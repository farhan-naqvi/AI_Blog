# Local Ollama worker

The worker authenticates to Supabase with the service-role key from the owner machine, atomically claims up to five jobs using `FOR UPDATE SKIP LOCKED`, and processes them serially to limit local resource pressure.

For each job it:

1. Loads metadata and validates the public URL.
2. Honors `robots.txt`, response timeouts, content types, redirects, and size limits.
3. Extracts up to 40,000 characters in memory with Trafilatura.
4. Requests JSON-schema output from the configured Ollama model.
5. Retries invalid structured output once.
6. Rejects invented evidence URLs or source IDs.
7. Applies deterministic publication rules and persists the final development.
8. Clears the temporary text variable and completes or requeues the job.

Run continuously:

```powershell
signalwatch worker --watch --interval 60
```

Use Windows Task Scheduler to start this command at sign-in with restart-on-failure enabled. When Ollama is unavailable, the current job is returned to the queue with bounded exponential backoff; cloud collection is unaffected.

`OLLAMA_MODEL` is configuration, not a claimed capability. Test the chosen local model for reliable JSON output before enabling automatic publication.
