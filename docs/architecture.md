# Architecture

## Runtime split

```text
GitHub Actions                      Owner computer
RSS/API collectors                 Ollama + local worker
       │                                  │
       ├── normalize/filter/dedupe        ├── atomic claim
       └── queue in Supabase ─────────────┤
                                          ├── safe fetch + robots check
Public React UI ◀── verified records ─────┤
Private owner UI ◀── RLS-protected data   └── validate/verify/persist
```

Supabase is the durable coordination layer. Cloud collectors require no model and continue while the owner machine is offline. The local worker is pull-based, so no inbound connection to the owner network is required.

## Trust boundaries

- The browser receives only the Supabase anon key. RLS is authoritative.
- Owner UI reads or changes private tables only with an authenticated owner JWT.
- GitHub Actions and the local worker use the service-role key outside the browser.
- Ollama is called only through its local HTTP interface.
- Source documents are bounded, checked against `robots.txt`, extracted locally, truncated, and never stored as bodies or raw HTML.

## Publication path

The model emits schema-constrained JSON. Pydantic rejects missing evidence, oversized fields, invented evidence references, and unsupported dates. Deterministic code then requires strong primary evidence, no contradiction, no unresolved duplicate, complete fields, and Major or Notable importance. Sensitive categories always become exceptions.

## Deliberate MVP limits

- No embeddings, vector database, knowledge graph, multi-user workspace, or automatic LinkedIn publishing.
- Sitemap and controlled-HTML source rows are seeded but paused until each site is reviewed. Implemented active connectors are RSS, GitHub releases, arXiv, and Hugging Face Hub.
- FastAPI is a small optional health/admin service; collection uses the Supabase repository directly to avoid requiring another always-on paid host.
