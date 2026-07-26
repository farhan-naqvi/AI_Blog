from typing import Any

from pydantic import BaseModel

from .collection import CollectionService
from .collectors import ArxivCollector, GitHubCollector, HuggingFaceCollector, RssCollector
from .config import Settings
from .coverage import PUBLIC_CATEGORIES, source_category
from .llm import ModelUnavailableError, OllamaProvider, StructuredGenerationError
from .repository import SupabaseRepository

SMOKE_CONNECTORS = ("rss", "github", "arxiv", "huggingface")
SMOKE_MAX_ITEMS = 3
COVERAGE_SOURCE_LIMITS = {
    "Models": 3,
    "Agents and developer tools": 3,
    "Research and AI science": 3,
    "Infrastructure and hardware": 2,
    "Business and products": 2,
    "Policy, safety and security": 2,
}


class OllamaDiagnosticOutput(BaseModel):
    ok: bool


async def smoke_test_collectors(
    repository: SupabaseRepository, settings: Settings
) -> dict[str, Any]:
    github_token = settings.github_token.get_secret_value() if settings.github_token else None
    hf_token = settings.huggingface_token.get_secret_value() if settings.huggingface_token else None
    collectors = {
        "rss": RssCollector(max_items=SMOKE_MAX_ITEMS),
        "github": GitHubCollector(github_token, max_items=SMOKE_MAX_ITEMS),
        "arxiv": ArxivCollector(max_items=SMOKE_MAX_ITEMS),
        "huggingface": HuggingFaceCollector(hf_token, max_items=SMOKE_MAX_ITEMS),
    }
    service = CollectionService(repository, collectors, concurrency=1)
    per_connector: dict[str, dict[str, int | str]] = {}
    totals = {
        "sources_checked": 0,
        "items_detected": 0,
        "items_new": 0,
        "jobs_created": 0,
        "errors": 0,
        "items_filtered": 0,
        "duplicates": 0,
        "items_clustered": 0,
    }
    for key in SMOKE_CONNECTORS:
        source = await repository.smoke_source(key)
        if source is None:
            result = {
                "sources_checked": 0,
                "items_detected": 0,
                "items_new": 0,
                "jobs_created": 0,
                "errors": 1,
                "items_filtered": 0,
                "duplicates": 0,
            }
            per_connector[key] = result | {"status": "missing_active_source"}
        else:
            result = await service.run_sources([source])
            per_connector[key] = result | {"status": "ok" if result["errors"] == 0 else "failed"}
        for metric in totals:
            totals[metric] += int(result.get(metric, 0))
    return {
        "mode": "smoke",
        "max_items_per_connector": SMOKE_MAX_ITEMS,
        "connectors": per_connector,
        "totals": totals,
    }


async def check_ollama(base_url: str, model: str) -> dict[str, Any]:
    try:
        provider = OllamaProvider(base_url, model, max_attempts=1, num_predict=24)
    except ValueError as exc:
        return {"ok": False, "reachable": False, "model_available": False, "error": str(exc)}
    try:
        try:
            installed = await provider.installed_models()
        except ModelUnavailableError:
            return {"ok": False, "reachable": False, "model_available": False}
        model_available = model in installed
        if not model_available:
            return {"ok": False, "reachable": True, "model_available": False, "model": model}
        try:
            result = await provider.generate_structured(
                'Return exactly {"ok":true}.', OllamaDiagnosticOutput
            )
            return {
                "ok": result.ok,
                "reachable": True,
                "model_available": True,
                "structured_output_valid": result.ok,
                "model": model,
            }
        except (ModelUnavailableError, StructuredGenerationError) as exc:
            return {
                "ok": False,
                "reachable": True,
                "model_available": True,
                "structured_output_valid": False,
                "error_type": type(exc).__name__,
                "model": model,
            }
    finally:
        await provider.close()


async def coverage_audit(repository: SupabaseRepository) -> dict[str, Any]:
    sources = await repository.coverage_sources(active_only=False)
    configured = {category: 0 for category in PUBLIC_CATEGORIES}
    active = {category: 0 for category in PUBLIC_CATEGORIES}
    connectors: set[str] = set()
    for source in sources:
        category = source_category(source)
        configured[category] += 1
        if source.active:
            active[category] += 1
            connectors.add(source.connector_key)
    return {
        "configured_total": len(sources),
        "active_total": sum(active.values()),
        "configured_by_category": configured,
        "active_by_category": active,
        "implemented_connector_types": sorted(connectors),
        "insufficient_categories": [category for category, count in active.items() if count < 5],
    }


async def bounded_category_collection(
    repository: SupabaseRepository, settings: Settings
) -> dict[str, Any]:
    sources = await repository.coverage_sources(active_only=True)
    selected: list = []
    counts = {category: 0 for category in PUBLIC_CATEGORIES}
    for source in sources:
        category = source_category(source)
        if counts[category] < COVERAGE_SOURCE_LIMITS[category]:
            selected.append(source)
            counts[category] += 1
    github_token = settings.github_token.get_secret_value() if settings.github_token else None
    hf_token = settings.huggingface_token.get_secret_value() if settings.huggingface_token else None
    service = CollectionService(
        repository,
        {
            "rss": RssCollector(max_items=10),
            "github": GitHubCollector(github_token, max_items=10),
            "arxiv": ArxivCollector(max_items=10),
            "huggingface": HuggingFaceCollector(hf_token, max_items=10),
        },
        concurrency=1,
    )
    result = await service.run_sources(selected)
    return {
        "mode": "bounded-category",
        "max_sources_per_category": 3,
        "max_items_per_source": 10,
        "max_raw_entries": 150,
        "selected_sources_by_category": counts,
        **result,
    }
