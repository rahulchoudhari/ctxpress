from typing import Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: Literal["claude", "claude-cli", "openai", "gemini", "custom"] = "claude"

    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    custom_base_url: str = "http://localhost:11434/v1"
    custom_api_key: Optional[str] = None
    custom_model: str = "llama3"

    claude_model: str = "claude-sonnet-4-5"
    openai_model: str = "gpt-4o"
    gemini_model: str = "gemini-2.5-flash"

    rtk_enabled: bool = True
    rtk_level: str = "default"

    caveman_enabled: bool = True
    caveman_level: Literal["lite", "full", "ultra"] = "full"

    prompt_opt_enabled: bool = True
    keep_context_between_messages: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
