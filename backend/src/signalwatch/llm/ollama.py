import json

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
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_identifier = model
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(180.0))
        self.max_attempts = max_attempts

    async def close(self) -> None:
        await self.client.aclose()

    async def available(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/api/tags", timeout=3.0)
            return response.is_success
        except httpx.HTTPError:
            return False

    async def generate_structured(self, prompt: str, schema: type[T]) -> T:
        last_error = "unknown validation error"
        repair = ""
        for _ in range(self.max_attempts):
            try:
                response = await self.client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model_identifier,
                        "stream": False,
                        "format": schema.model_json_schema(),
                        "options": {"temperature": 0.1, "num_predict": 1800},
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Return only JSON matching the supplied schema. Use only the "
                                    "provided evidence. Never invent URLs, dates, claims, or metrics."
                                ),
                            },
                            {"role": "user", "content": prompt + repair},
                        ],
                    },
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ModelUnavailableError(f"Ollama unavailable: {exc}") from exc
            try:
                content = response.json()["message"]["content"]
                return schema.model_validate(json.loads(content))
            except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
                repair = (
                    "\n\nYour previous output was invalid. Return a corrected JSON object only. "
                    f"Validation error: {last_error[:700]}"
                )
        raise StructuredGenerationError(last_error)
