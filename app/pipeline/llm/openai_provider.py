from typing import AsyncIterator

from openai import AsyncOpenAI

from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
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
            stream_options={"include_usage": True},
        )

        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if chunk.usage:
                self._last_usage = {
                    "input_tokens": chunk.usage.prompt_tokens or 0,
                    "output_tokens": chunk.usage.completion_tokens or 0,
                }

    async def get_usage(self) -> dict:
        return self._last_usage

    def provider_name(self) -> str:
        return "openai"

    def model_name(self) -> str:
        return self.model
