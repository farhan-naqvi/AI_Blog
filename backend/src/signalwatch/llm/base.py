import json
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelUnavailableError(RuntimeError):
    pass


class StructuredGenerationError(RuntimeError):
    def __init__(
        self,
        reason: str,
        *,
        errors: list[dict[str, Any]] | None = None,
        json_valid: bool | None = None,
        additional_prose: bool = False,
    ) -> None:
        self.reason = reason
        self.errors = errors or []
        self.json_valid = json_valid
        self.additional_prose = additional_prose
        super().__init__(
            json.dumps(
                {
                    "reason": reason,
                    "errors": self.errors,
                    "json_valid": json_valid,
                    "additional_prose": additional_prose,
                },
                separators=(",", ":"),
            )
        )


class LanguageModelProvider(Protocol):
    model_identifier: str

    async def generate_structured(self, prompt: str, schema: type[T]) -> T:
        ...
