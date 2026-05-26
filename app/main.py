import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from .config import Settings

# Mutable settings container - use get_settings() to access
_current_settings = Settings()


def get_settings():
    return _current_settings
from .models import ChatRequest, SettingsResponse, SettingsUpdate
from .pipeline.caveman import compress_context
from .pipeline.context import MAX_FILE_SIZE, ContextItem, classify_file, collect_context, is_sensitive, normalize_content
from .pipeline.llm import create_provider
from .pipeline.prompt_opt import optimize_user_prompt
from .pipeline.rtk_filter import filter_context, rtk_available
from .pipeline.tokencount import count_tokens

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Token Optimizer", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"


def build_system_prompt(items: list) -> str:
    if not items:
        return ""

    parts = ["Here is the relevant context:\n"]
    for item in items:
        if not item.content:
            continue
        label = f"[{item.path}]"
        if item.language:
            label += f" ({item.language})"
        parts.append(f"--- {label} ---\n{item.content}\n")

    parts.append("---\nUse the context above to answer the user's question. Be concise and accurate.")
    return "\n".join(parts)


def build_uploaded_context(uploaded_files: list) -> list[ContextItem]:
    """Build context items from browser-uploaded file payloads."""
    items: list[ContextItem] = []
    for uploaded in uploaded_files:
        path_str = uploaded.path.strip()
        if not path_str:
            continue

        pseudo_path = Path(path_str)

        if is_sensitive(pseudo_path):
            items.append(ContextItem(
                path=path_str,
                content="",
                is_code=False,
                warnings=[f"Skipped sensitive file: {pseudo_path.name}"],
            ))
            continue

        if len(uploaded.content.encode("utf-8", errors="replace")) > MAX_FILE_SIZE:
            items.append(ContextItem(
                path=path_str,
                content="",
                is_code=False,
                warnings=[f"Skipped (>{MAX_FILE_SIZE // 1000}KB): {pseudo_path.name}"],
            ))
            continue

        normalized = normalize_content(pseudo_path, uploaded.content)
        is_code, language = classify_file(pseudo_path)
        items.append(ContextItem(
            path=path_str,
            content=normalized,
            is_code=is_code,
            language=language,
        ))

    return items


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    req = ChatRequest(**body)

    # Capture settings at request time
    current = get_settings()

    # Allow per-request overrides
    use_rtk = req.rtk_enabled if req.rtk_enabled is not None else current.rtk_enabled
    use_caveman = req.caveman_enabled if req.caveman_enabled is not None else current.caveman_enabled
    caveman_level = req.caveman_level or current.caveman_level
    use_prompt_opt = req.prompt_opt_enabled if req.prompt_opt_enabled is not None else current.prompt_opt_enabled

    async def event_generator():
        stats = {
            "original_tokens": 0,
            "after_rtk_tokens": 0,
            "after_caveman_tokens": 0,
            "final_tokens": 0,
            "savings_percent": 0.0,
        }
        stage_info = {
            "rtk_enabled": bool(use_rtk),
            "rtk_available": False,
            "rtk_used": False,
            "caveman_enabled": bool(use_caveman),
            "caveman_used": False,
            "prompt_opt_enabled": bool(use_prompt_opt),
            "prompt_opt_used": False,
        }
        prompt_stats = {
            "original_tokens": count_tokens(req.message or ""),
            "optimized_tokens": count_tokens(req.message or ""),
            "tokens_delta": 0,
            "intent": "general",
        }

        try:
            # Phase 1: Context collection
            items = []
            if req.files or req.uploaded_files:
                yield {"event": "status", "data": json.dumps({"phase": "collecting", "message": "Collecting context..."})}

                uploaded_paths = {f.path for f in req.uploaded_files}

                if req.files:
                    filesystem_paths = [p for p in req.files if p not in uploaded_paths]
                    if filesystem_paths:
                        items.extend(await collect_context(filesystem_paths))

                if req.uploaded_files:
                    items.extend(build_uploaded_context(req.uploaded_files))

                # Report warnings
                for item in items:
                    for warning in item.warnings:
                        yield {"event": "warning", "data": json.dumps({"message": warning})}

                stats["original_tokens"] = sum(count_tokens(i.content) for i in items if i.content)

            # Phase 2: RTK filtering
            if items and use_rtk:
                stage_info["rtk_available"] = await rtk_available()
                yield {"event": "status", "data": json.dumps({"phase": "rtk", "message": "Filtering with RTK..."})}
                items = await filter_context(items, current.rtk_level)
                stage_info["rtk_used"] = stage_info["rtk_available"]
                stats["after_rtk_tokens"] = sum(count_tokens(i.content) for i in items if i.content)
            else:
                stats["after_rtk_tokens"] = stats["original_tokens"]

            # Phase 3: Caveman compression
            if items and use_caveman:
                yield {"event": "status", "data": json.dumps({"phase": "caveman", "message": "Compressing redundancy..."})}
                items = compress_context(items, level=caveman_level)
                stage_info["caveman_used"] = True
                stats["after_caveman_tokens"] = sum(count_tokens(i.content) for i in items if i.content)
            else:
                stats["after_caveman_tokens"] = stats["after_rtk_tokens"]

            stats["final_tokens"] = stats["after_caveman_tokens"]
            if stats["original_tokens"] > 0:
                saved = stats["original_tokens"] - stats["final_tokens"]
                stats["savings_percent"] = round((saved / stats["original_tokens"]) * 100, 1)

            system_prompt = build_system_prompt(items)
            user_message = req.message
            if use_prompt_opt and req.message:
                yield {"event": "status", "data": json.dumps({"phase": "prompt_opt", "message": "Optimizing prompt..."})}
                user_message, prompt_stats = optimize_user_prompt(req.message)
                stage_info["prompt_opt_used"] = True

            # Phase 4: LLM streaming
            yield {"event": "status", "data": json.dumps({"phase": "llm", "message": "Sending to LLM..."})}

            messages = [{"role": "user", "content": user_message}]

            provider = create_provider(current)

            async for chunk in provider.stream(messages, system=system_prompt):
                yield {"event": "token", "data": json.dumps({"text": chunk})}

            # Phase 5: Final stats
            usage = await provider.get_usage()
            yield {"event": "done", "data": json.dumps({
                "usage": usage,
                "stats": stats,
                "stage_info": stage_info,
                "prompt_stats": prompt_stats,
                "provider": provider.provider_name(),
                "model": provider.model_name(),
            })}

        except Exception as e:
            logger.exception("Pipeline error")
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

    return EventSourceResponse(event_generator())


@app.get("/api/settings")
async def read_settings():
    s = get_settings()
    return SettingsResponse(
        llm_provider=s.llm_provider,
        claude_model=s.claude_model,
        openai_model=s.openai_model,
        gemini_model=s.gemini_model,
        custom_base_url=s.custom_base_url,
        custom_model=s.custom_model,
        rtk_enabled=s.rtk_enabled,
        rtk_level=s.rtk_level,
        caveman_enabled=s.caveman_enabled,
        caveman_level=s.caveman_level,
        prompt_opt_enabled=s.prompt_opt_enabled,
        keep_context_between_messages=s.keep_context_between_messages,
        has_anthropic_key=bool(s.anthropic_api_key),
        has_openai_key=bool(s.openai_api_key),
        has_gemini_key=bool(s.gemini_api_key),
        has_custom_key=bool(s.custom_api_key),
    )


@app.post("/api/settings")
async def update_settings(request: Request):
    body = await request.json()
    update = SettingsUpdate(**body)

    # Update .env file
    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text("")

    env_lines = env_path.read_text().splitlines()
    env_map = {}
    for line in env_lines:
        if "=" in line and not line.strip().startswith("#"):
            key, _, val = line.partition("=")
            env_map[key.strip()] = val.strip()

    field_to_env = {
        "llm_provider": "LLM_PROVIDER",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
        "gemini_api_key": "GEMINI_API_KEY",
        "custom_base_url": "CUSTOM_BASE_URL",
        "custom_api_key": "CUSTOM_API_KEY",
        "custom_model": "CUSTOM_MODEL",
        "claude_model": "CLAUDE_MODEL",
        "openai_model": "OPENAI_MODEL",
        "gemini_model": "GEMINI_MODEL",
        "rtk_enabled": "RTK_ENABLED",
        "rtk_level": "RTK_LEVEL",
        "caveman_enabled": "CAVEMAN_ENABLED",
        "caveman_level": "CAVEMAN_LEVEL",
        "prompt_opt_enabled": "PROMPT_OPT_ENABLED",
        "keep_context_between_messages": "KEEP_CONTEXT_BETWEEN_MESSAGES",
    }

    for field_name, env_key in field_to_env.items():
        val = getattr(update, field_name, None)
        if val is not None:
            env_map[env_key] = str(val).lower() if isinstance(val, bool) else str(val)

    # Write back
    lines = []
    for key, val in env_map.items():
        lines.append(f"{key}={val}")
    env_path.write_text("\n".join(lines) + "\n")

    # Reload: re-read .env into os.environ, then rebuild Settings
    load_dotenv(override=True)
    global _current_settings
    _current_settings = Settings()

    logger.info(f"Settings reloaded: provider={_current_settings.llm_provider}")
    return {"status": "ok"}


@app.get("/api/rtk-status")
async def rtk_status():
    available = await rtk_available()
    return {"available": available}
