"""
Claude CLI provider - uses your existing `claude` CLI authentication (OAuth).
No API key needed. Pipes prompts through `claude --print`.
"""

import asyncio
import logging
import shutil
from typing import AsyncIterator

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class ClaudeCLIProvider(BaseLLMProvider):
    def __init__(self, model: str = "claude-sonnet-4-5"):
        self.model = model
        self._last_usage: dict = {}
        self._cli_path = shutil.which("claude")
        if not self._cli_path:
            raise RuntimeError(
                "Claude CLI not found. Install it from https://docs.anthropic.com/en/docs/claude-code "
                "or use 'claude' provider with an API key instead."
            )

    async def stream(self, messages: list[dict], system: str = "") -> AsyncIterator[str]:
        # Build the prompt from messages and system
        prompt_parts = []
        if system:
            prompt_parts.append(f"[Context]\n{system}\n")
        for msg in messages:
            if msg["role"] == "user":
                prompt_parts.append(msg["content"])
        prompt = "\n\n".join(prompt_parts)

        # Use claude CLI with --print flag (non-interactive, uses existing OAuth)
        args = [self._cli_path, "--print", "--model", self.model]

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Send prompt via stdin
        stdout, stderr = await proc.communicate(input=prompt.encode("utf-8"))

        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"Claude CLI failed (exit {proc.returncode}): {err}")

        output = stdout.decode("utf-8", errors="replace")

        # Estimate tokens (CLI doesn't report usage directly)
        self._last_usage = {
            "input_tokens": len(prompt) // 4,  # rough estimate
            "output_tokens": len(output) // 4,
        }

        # Yield output in chunks to simulate streaming
        chunk_size = 50
        for i in range(0, len(output), chunk_size):
            yield output[i:i + chunk_size]

    async def get_usage(self) -> dict:
        return self._last_usage

    def provider_name(self) -> str:
        return "claude-cli"

    def model_name(self) -> str:
        return self.model
