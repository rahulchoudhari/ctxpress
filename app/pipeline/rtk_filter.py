import asyncio
import logging
import shutil
from pathlib import Path
from typing import Optional

from .context import ContextItem

logger = logging.getLogger(__name__)

_rtk_path: Optional[str] = None
_rtk_checked = False
_semaphore = asyncio.Semaphore(10)

RTK_TIMEOUT = 10  # seconds


async def rtk_available() -> bool:
    global _rtk_path, _rtk_checked
    if _rtk_checked:
        return _rtk_path is not None

    _rtk_path = shutil.which("rtk")
    _rtk_checked = True

    if _rtk_path:
        logger.info(f"RTK found at: {_rtk_path}")
    else:
        logger.info(
            "RTK not installed. Context will be passed unfiltered. "
            "Install: brew install rtk"
        )
    return _rtk_path is not None


async def _run_rtk(args: list[str]) -> Optional[str]:
    if not _rtk_path:
        return None

    async with _semaphore:
        try:
            proc = await asyncio.create_subprocess_exec(
                _rtk_path, *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=RTK_TIMEOUT
            )
            if proc.returncode == 0:
                return stdout.decode("utf-8", errors="replace")
            else:
                logger.warning(f"RTK error (exit {proc.returncode}): {stderr.decode(errors='replace')[:200]}")
                return None
        except asyncio.TimeoutError:
            logger.warning(f"RTK timeout after {RTK_TIMEOUT}s: rtk {' '.join(args)}")
            proc.kill()
            return None
        except Exception as e:
            logger.warning(f"RTK exception: {e}")
            return None


async def rtk_filter_file(path: str, level: str = "default") -> Optional[str]:
    args = ["read", path]
    if level == "aggressive":
        args.extend(["-l", "aggressive"])
    return await _run_rtk(args)


async def rtk_smart_summary(path: str) -> Optional[str]:
    return await _run_rtk(["smart", path])


async def rtk_filter_directory(path: str) -> Optional[str]:
    return await _run_rtk(["ls", path])


async def filter_context(items: list[ContextItem], level: str = "default") -> list[ContextItem]:
    if not await rtk_available():
        return items

    async def process(item: ContextItem) -> ContextItem:
        if not item.content or not item.path:
            return item

        # Browser-uploaded files may have virtual paths that don't exist on server disk.
        if not Path(item.path).expanduser().exists():
            return item

        filtered = await rtk_filter_file(item.path, level)
        if filtered is not None:
            return ContextItem(
                path=item.path,
                content=filtered,
                is_code=item.is_code,
                language=item.language,
                warnings=item.warnings,
            )
        return item

    results = await asyncio.gather(*[process(item) for item in items])
    return list(results)
