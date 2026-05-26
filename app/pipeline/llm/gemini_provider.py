import asyncio
from typing import AsyncIterator

from google import genai

from .base import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self._last_usage: dict = {}

    async def stream(self, messages: list[dict], system: str = "") -> AsyncIterator[str]:
        contents = []
        if system:
            contents.append({"role": "user", "parts": [{"text": f"[System Instructions]\n{system}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will follow these instructions."}]})

        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        # Run sync streaming in a thread to keep async event loop free
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.model,
            contents=contents,
            config={"response_modalities": ["TEXT"]},
        )

        if response.text:
            yield response.text

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            self._last_usage = {
                "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
            }

    async def get_usage(self) -> dict:
        return self._last_usage

    def provider_name(self) -> str:
        return "gemini"

    def model_name(self) -> str:
        return self.model
