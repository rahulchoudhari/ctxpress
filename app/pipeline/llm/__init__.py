from .base import BaseLLMProvider
from .claude_provider import ClaudeProvider
from .claude_cli_provider import ClaudeCLIProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .custom_provider import CustomProvider


def create_provider(settings) -> BaseLLMProvider:
    provider = settings.llm_provider

    if provider == "claude":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not set. Use 'claude-cli' provider to authenticate via your existing Claude login.")
        return ClaudeProvider(settings.anthropic_api_key, settings.claude_model)
    elif provider == "claude-cli":
        return ClaudeCLIProvider(settings.claude_model)
    elif provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not set")
        return OpenAIProvider(settings.openai_api_key, settings.openai_model)
    elif provider == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set")
        return GeminiProvider(settings.gemini_api_key, settings.gemini_model)
    elif provider == "custom":
        return CustomProvider(
            settings.custom_base_url,
            settings.custom_api_key,
            settings.custom_model,
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")
