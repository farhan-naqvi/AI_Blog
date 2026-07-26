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

The curated registry includes 80 sources. Fifty-one are active through the tested RSS/Atom, GitHub, arXiv, and Hugging Face connectors; review-dependent sitemap, HTML, government API, and discovery connectors remain paused. Every source has one public category in `connector_config.public_category`.

Manual coverage collection is bounded to 150 raw entries: at most three selected sources per category in the current command and ten entries per source. Candidate queue ceilings are Models 15, Agents/developer tools 15, Research 20, Infrastructure 10, Business/products 10, and Policy/safety/security 10. These are safety ceilings, never quotas.

Focused arXiv streams combine reviewed categories with topic keywords. Cross-source candidates receive a deterministic cluster key from release version/product metadata or normalized title tokens and date proximity. Exact duplicates still use canonical URL, source identifier, content hash, and title hash; clustering never merges events based only on a company name.

Enable a paused source only after confirming its permitted retrieval path, freshness signal, meaningful development-level output, and tested connector behavior.

## Hugging Face discovery filtering

Hugging Face remains a discovery-quality connector. It orders by model creation time and queues only recent models with a recognized task plus a model card, description, or explicit paper/repository metadata. Generic updates, stale models, mirrors, and common quantized variants are filtered before database insertion.

Per-source `connector_config` may override `max_model_age_days` (default 90), `new_model_window_days` (default 30), `task_tags`, `reject_variants`, `require_model_card`, and `watchlist`. Popularity metrics may be retained as short context, but no universal download or like threshold is applied by default.

GitHub releases retain only bounded connector metadata: repository, organisation, tag, release title, published date, prerelease state, and whether the URL is an official primary repository release. The worker revalidates the repository and tag against the canonical GitHub URL before composing observable release facts. A complete official non-prerelease release at semantic version 2 or later may receive a deterministic **Notable** floor when the model returns Incremental; deterministic code never assigns **Major** from version metadata alone. Performance and capability statements remain source-reported claims.
