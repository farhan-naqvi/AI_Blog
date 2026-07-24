from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelUnavailableError(RuntimeError):
    pass


class StructuredGenerationError(RuntimeError):
    pass


class LanguageModelProvider(Protocol):
    model_identifier: str

    async def generate_structured(self, prompt: str, schema: type[T]) -> T:
        ...
