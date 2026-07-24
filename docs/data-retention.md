# Data retention

`cleanup_expired_data()` runs hourly through `pg_cron`.

| Data | Retention |
| --- | --- |
| Temporary readable source text | Memory only; discarded after each job |
| Unpinned LinkedIn drafts | 48 hours |
| Published unpinned draft content | Scrubbed immediately; fingerprint/URL metadata may remain until expiry |
| Rejected or irrelevant source items | 7 days |
| Expired pending jobs | 7-day maximum age, then removed and source item rejected |
| Completed jobs | 7 days |
| Failed/dead jobs | 14 days |
| Operational logs | 7 days |
| Resolved exceptions | 30 days |
| Published developments and reports | Permanent |
| Linked supporting source metadata | Permanent |

The schema intentionally has no full-article, raw-HTML, prompt-conversation, chain-of-thought, image-copy, embedding, or page-snapshot storage.
