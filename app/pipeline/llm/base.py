from abc import ABC, abstractmethod
from typing import AsyncIterator


class BaseLLMProvider(ABC):
    @abstractmethod
    async def stream(self, messages: list[dict], system: str = "") -> AsyncIterator[str]:
        """Yield text chunks as they stream from the LLM."""
        ...

    @abstractmethod
    async def get_usage(self) -> dict:
        """Return usage stats from the last stream call."""
        ...

    @abstractmethod
    def provider_name(self) -> str:
        ...

    @abstractmethod
    def model_name(self) -> str:
        ...
