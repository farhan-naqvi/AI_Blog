# Source policy

Retrieval priority is official API, RSS/Atom, sitemap/change detection, then reviewed lightweight HTML extraction. A source record describes ownership, retrieval method, reliability, primary status, interval, rate ceiling, conditional-request metadata, health, and active state.

## Allowed

- Public official APIs and feeds
- Public research APIs
- Official repositories and release APIs
- Public sitemaps after review
- Lightweight page extraction where terms and robots policy permit it

## Prohibited

- LinkedIn and X/Twitter scraping
- Search-result scraping
- Crunchbase, PitchBook, Dealroom, paywalled publishers, or restricted platforms
- Bypassing access controls or robots rules
- Treating a discovery signal as primary evidence when an official source exists

The seed registry includes 41 sources. Twenty-one use implemented connectors and are active; review-dependent sitemap, HTML, government, and discovery connectors are paused. Enable a paused source only after confirming its permitted retrieval path and adding a tested connector.

## Hugging Face discovery filtering

Hugging Face remains a discovery-quality connector. It orders by model creation time and queues only recent models with a recognized task plus a model card, description, or explicit paper/repository metadata. Generic updates, stale models, mirrors, and common quantized variants are filtered before database insertion.

Per-source `connector_config` may override `max_model_age_days` (default 90), `new_model_window_days` (default 30), `task_tags`, `reject_variants`, `require_model_card`, and `watchlist`. Popularity metrics may be retained as short context, but no universal download or like threshold is applied by default.
