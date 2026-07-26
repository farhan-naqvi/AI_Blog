from typing import Any

from pydantic import BaseModel

from .collection import CollectionService
from .collectors import ArxivCollector, GitHubCollector, HuggingFaceCollector, RssCollector
from .config import Settings
from .llm import ModelUnavailableError, OllamaProvider, StructuredGenerationError
from .repository import SupabaseRepository

SMOKE_CONNECTORS = ("rss", "github", "arxiv", "huggingface")
SMOKE_MAX_ITEMS = 3


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
