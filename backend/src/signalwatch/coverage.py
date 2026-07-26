import re
from collections import Counter
from hashlib import sha256

from .models import CollectedItem, SourceRecord

MODELS = "Models"
AGENTS = "Agents and developer tools"
RESEARCH = "Research and AI science"
INFRASTRUCTURE = "Infrastructure and hardware"
BUSINESS = "Business and products"
POLICY = "Policy, safety and security"

PUBLIC_CATEGORIES = (MODELS, AGENTS, RESEARCH, INFRASTRUCTURE, BUSINESS, POLICY)
CANDIDATE_LIMITS = {
    MODELS: 15,
    AGENTS: 15,
    RESEARCH: 20,
    INFRASTRUCTURE: 10,
    BUSINESS: 10,
    POLICY: 10,
}
PROCESSING_QUOTAS = {MODELS: 4, AGENTS: 4, RESEARCH: 4, INFRASTRUCTURE: 3, BUSINESS: 3, POLICY: 2}

_GENERIC = {
    "about", "after", "with", "from", "into", "that", "this", "their", "release",
    "released", "announces", "introducing", "update", "version", "official", "github",
}
_CATEGORY_TERMS = {
    MODELS: ("model", "llama", "gemma", "qwen", "mistral", "deepseek", "checkpoint", "weights", "license"),
    AGENTS: ("agent", "sdk", "framework", "tool", "runtime", "api", "workflow", "server", "client"),
    INFRASTRUCTURE: ("gpu", "accelerator", "inference", "training", "runtime", "distributed", "hardware", "cloud", "benchmark"),
    BUSINESS: ("launch", "acquisition", "acquire", "partnership", "pricing", "availability", "funding"),
    POLICY: ("regulation", "guidance", "consultation", "standard", "advisory", "security", "policy", "enforcement", "act"),
}


def source_category(source: SourceRecord | dict) -> str:
    config = source.connector_config if isinstance(source, SourceRecord) else source.get("connector_config", {})
    configured = config.get("public_category")
    if configured in PUBLIC_CATEGORIES:
        return configured
    key = source.connector_key if isinstance(source, SourceRecord) else source.get("connector_key")
    name = (source.name if isinstance(source, SourceRecord) else source.get("name", "")).casefold()
    source_type = (source.source_type if isinstance(source, SourceRecord) else source.get("source_type", "")).casefold()
    if key == "arxiv" or "research" in source_type:
        return RESEARCH
    if key == "huggingface" or any(word in name for word in ("llama", "qwen", "model", "openai", "mistral")):
        return MODELS
    if any(word in name for word in ("nist", "cisa", "enisa", "eur-lex", "policy", "ai office", "security institute", "oecd", "data protection")):
        return POLICY
    if any(word in name for word in ("nvidia", "pytorch", "tensorflow", "jax", "vllm", "ollama", "llama.cpp", "tensorrt", "cloudflare", "databricks", "aws")):
        return INFRASTRUCTURE
    if key == "github" or "open source" in source_type:
        return AGENTS
    return BUSINESS


def development_category(row: dict) -> str:
    configured = row.get("public_category")
    if configured in PUBLIC_CATEGORIES:
        return configured
    category = row.get("category")
    event_type = row.get("event_type")
    if category == "Models":
        return MODELS
    if category in {"Agents", "Developer tools"}:
        return AGENTS
    if category in {"Research", "Robotics"}:
        return RESEARCH
    if category == "Infrastructure":
        return INFRASTRUCTURE
    if category in {"Regulation", "Security"}:
        return POLICY
    if event_type in {"Partnership", "Funding"} or category == "Other":
        return BUSINESS
    return BUSINESS


def category_rejection_reason(item: CollectedItem, category: str, config: dict | None = None) -> str | None:
    text = f"{item.title} {item.excerpt}".casefold()
    config = config or {}
    if category == RESEARCH:
        if item.event_type_hint != "research" or len(item.excerpt.strip()) < int(config.get("minimum_abstract_chars", 180)):
            return "insufficient_research_abstract"
        keywords = [str(value).casefold() for value in config.get("keywords", [])]
        if keywords and not any(keyword in text for keyword in keywords):
            return "outside_focused_research_topic"
        return None
    if category == AGENTS and item.event_type_hint == "release":
        if not item.excerpt.strip():
            return "empty_release"
        if re.search(r"\b(?:deps?|dependencies|housekeeping|documentation only)\b", text):
            return "routine_maintenance"
    terms = _CATEGORY_TERMS.get(category)
    if terms and not any(term in text for term in terms):
        return f"weak_{category.split()[0].casefold()}_signal"
    return None


def deterministic_cluster_key(item: CollectedItem, source: SourceRecord) -> str | None:
    title = item.title.casefold()
    version = re.search(r"\bv?\d+(?:\.\d+){1,3}\b", title)
    tokens = [token for token in re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", title) if token not in _GENERIC]
    if len(tokens) < 2:
        return None
    if version:
        preceding = title[: version.start()]
        preceding_tokens = re.findall(r"[a-z0-9][a-z0-9.+-]{2,}", preceding)
        product = preceding_tokens[-1] if preceding_tokens else tokens[0]
        raw = f"version|{product}|{version.group(0).removeprefix('v')}"
        return sha256(raw.encode()).hexdigest()
    key_tokens = sorted(set(tokens[:6]))
    date_bucket = item.published_at.date().isoformat() if item.published_at else "undated"
    return sha256(f"{date_bucket}|{'|'.join(key_tokens)}".encode()).hexdigest()


def select_balanced(rows: list[dict], limit: int, quotas: dict[str, int] | None = None) -> list[dict]:
    quotas = quotas or PROCESSING_QUOTAS
    counts: Counter[str] = Counter()
    selected: list[dict] = []
    for row in rows:
        category = row.get("public_category")
        if category not in quotas or counts[category] >= quotas[category]:
            continue
        selected.append(row)
        counts[category] += 1
        if len(selected) >= limit:
            break
    return selected
