from typing import AsyncIterator

import anthropic

from .base import BaseLLMProvider


class ClaudeProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._last_usage: dict = {}

    async def stream(self, messages: list[dict], system: str = "") -> AsyncIterator[str]:
        kwargs = {
            "model": self.model,
            "max_tokens": 8192,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        async with self.client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

            msg = await stream.get_final_message()
            self._last_usage = {
                "input_tokens": msg.usage.input_tokens,
                "output_tokens": msg.usage.output_tokens,
            }

    async def get_usage(self) -> dict:
        return self._last_usage

    def provider_name(self) -> str:
        return "claude"

    def model_name(self) -> str:
        return self.model
