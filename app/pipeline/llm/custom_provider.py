from typing import AsyncIterator

from openai import AsyncOpenAI

from .base import BaseLLMProvider


class CustomProvider(BaseLLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str):
        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
        )
        self.model = model
        self._last_usage: dict = {}

    async def stream(self, messages: list[dict], system: str = "") -> AsyncIterator[str]:
        chat_messages = []
        if system:
            chat_messages.append({"role": "system", "content": system})
        chat_messages.extend(messages)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=chat_messages,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if hasattr(chunk, "usage") and chunk.usage:
                self._last_usage = {
                    "input_tokens": getattr(chunk.usage, "prompt_tokens", 0) or 0,
                    "output_tokens": getattr(chunk.usage, "completion_tokens", 0) or 0,
                }

    async def get_usage(self) -> dict:
        return self._last_usage

    def provider_name(self) -> str:
        return "custom"

    def model_name(self) -> str:
        return self.model
