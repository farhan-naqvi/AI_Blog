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

Run one job or a bounded pass (jobs are claimed one at a time):

```powershell
python -m signalwatch.cli worker --max-jobs 1
python -m signalwatch.cli worker --max-jobs 5
```

Before starting the worker, verify Ollama without downloading a model:

```powershell
python -m signalwatch.cli check-ollama
```

The command checks the local endpoint, confirms the configured model is installed, performs one tiny schema-constrained request, and returns compact JSON. Install or start Ollama yourself if it reports `reachable:false`; SignalWatch never pulls a model automatically.

After the database smoke collection has created a pending job, run exactly one controlled end-to-end item:

```powershell
python -m signalwatch.cli e2e-verify
```

It atomically claims one job and reports each state without printing database IDs. Publication remains subject to the normal deterministic rules; a legitimate outcome may be `Held`. If Ollama or extraction is unavailable before completion, the job is requeued with bounded backoff.

Use Windows Task Scheduler to start this command at sign-in with restart-on-failure enabled. When Ollama is unavailable, the current job is returned to the queue with bounded exponential backoff; cloud collection is unaffected.

`OLLAMA_MODEL` is configuration, not a claimed capability. Test the chosen local model for reliable JSON output before enabling automatic publication.
