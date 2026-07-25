import json
from typing import Any
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ValidationError

from .base import ModelUnavailableError, StructuredGenerationError, T


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        client: httpx.AsyncClient | None = None,
        max_attempts: int = 2,
        num_predict: int = 1800,
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("OLLAMA_BASE_URL must use a loopback host")
        if parsed.username or parsed.password:
            raise ValueError("OLLAMA_BASE_URL must not contain credentials")
        self.base_url = base_url.rstrip("/")
        self.model_identifier = model
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(180.0))
        self.max_attempts = max(1, min(max_attempts, 2))
        self.num_predict = max(16, min(num_predict, 4096))
        self.last_repair_used = False

    async def close(self) -> None:
        await self.client.aclose()

    async def available(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=3.0)
            return response.is_success
        except httpx.HTTPError:
            return False

    async def installed_models(self) -> set[str]:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=3.0)
            response.raise_for_status()
            return {
                str(model.get("name") or model.get("model"))
                for model in response.json().get("models", [])
                if model.get("name") or model.get("model")
            }
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise ModelUnavailableError(f"Ollama unavailable: {exc}") from exc

    async def has_model(self, model: str) -> bool:
        return model in await self.installed_models()

    async def generate_structured(self, prompt: str, schema: type[T]) -> T:
        self.last_repair_used = False
        content = await self._chat(prompt, schema)
        payload = self._decode_json(content)
        try:
            return schema.model_validate(payload)
        except ValidationError as exc:
            errors = _validation_errors(exc)
            if self.max_attempts == 1:
                raise StructuredGenerationError(
                    "schema_validation", errors=errors, json_valid=True
                ) from exc
        repair_prompt = (
            "Correct structure only. Do not add facts. The target JSON schema is supplied in the "
            "request format. Return only the corrected object.\nINVALID_OBJECT:\n"
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:6000]
            + "\nFIELD_ERRORS:\n"
            + json.dumps(errors, separators=(",", ":"))
        )
        self.last_repair_used = True
        repaired_content = await self._chat(repair_prompt, schema)
        repaired_payload = self._decode_json(repaired_content)
        try:
            return schema.model_validate(repaired_payload)
        except ValidationError as exc:
            raise StructuredGenerationError(
                "repair_failed", errors=_validation_errors(exc), json_valid=True
            ) from exc

    async def _chat(self, prompt: str, schema: type[BaseModel]) -> str:
        schema_limits = {"FactualExtraction": 700, "DevelopmentAnalysis": 500}
        output_limit = min(self.num_predict, schema_limits.get(schema.__name__, self.num_predict))
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model_identifier,
                    "stream": False,
                    "think": False,
                    "format": schema.model_json_schema(),
                    "options": {"temperature": 0.0, "num_predict": output_limit},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Return only JSON matching the supplied schema. Use only supplied "
                                "evidence. Use null when unknown and empty arrays when unsupported. "
                                "Never invent dates, organisations, products, claims, or metrics."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            if not isinstance(content, str):
                raise TypeError("Ollama message content is not text")
            return content
        except httpx.HTTPError as exc:
            raise ModelUnavailableError(f"Ollama unavailable: {exc}") from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise StructuredGenerationError("malformed_ollama_response", json_valid=None) from exc

    @staticmethod
    def _decode_json(content: str) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise StructuredGenerationError(
                "invalid_json",
                errors=[{"field": "__root__", "type": "json_invalid", "category": "malformed"}],
                json_valid=False,
                additional_prose=exc.msg == "Extra data",
            ) from exc


def _validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        error_type = str(error["type"])
        if error_type == "missing":
            category = "missing"
        elif error_type in {"literal_error", "enum"}:
            category = "invalid_enum"
        elif "too_long" in error_type:
            category = "too_long"
        elif error_type.endswith("_type") or "parsing" in error_type:
            category = "wrong_type_or_malformed"
        else:
            category = "constraint_or_value"
        result.append(
            {
                "field": ".".join(str(part) for part in error["loc"]) or "__root__",
                "type": error_type,
                "category": category,
            }
        )
    return result
