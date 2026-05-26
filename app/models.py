from typing import Optional

from pydantic import BaseModel


class UploadedFile(BaseModel):
    path: str
    content: str


class ChatRequest(BaseModel):
    message: str
    files: list[str] = []
    uploaded_files: list[UploadedFile] = []
    provider: Optional[str] = None
    rtk_enabled: Optional[bool] = None
    caveman_enabled: Optional[bool] = None
    caveman_level: Optional[str] = None
    prompt_opt_enabled: Optional[bool] = None


class PipelineStats(BaseModel):
    original_tokens: int = 0
    after_rtk_tokens: int = 0
    after_caveman_tokens: int = 0
    final_tokens: int = 0
    savings_percent: float = 0.0


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    custom_base_url: Optional[str] = None
    custom_api_key: Optional[str] = None
    custom_model: Optional[str] = None
    claude_model: Optional[str] = None
    openai_model: Optional[str] = None
    gemini_model: Optional[str] = None
    rtk_enabled: Optional[bool] = None
    rtk_level: Optional[str] = None
    caveman_enabled: Optional[bool] = None
    caveman_level: Optional[str] = None
    prompt_opt_enabled: Optional[bool] = None
    keep_context_between_messages: Optional[bool] = None


class SettingsResponse(BaseModel):
    llm_provider: str
    claude_model: str
    openai_model: str
    gemini_model: str
    custom_base_url: str
    custom_model: str
    rtk_enabled: bool
    rtk_level: str
    caveman_enabled: bool
    caveman_level: str
    prompt_opt_enabled: bool
    keep_context_between_messages: bool
    has_anthropic_key: bool
    has_openai_key: bool
    has_gemini_key: bool
    has_custom_key: bool
