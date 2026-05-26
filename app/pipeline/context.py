import html
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

MAX_FILE_SIZE = 500_000  # 500KB

CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go", ".java", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".sh",
    ".bash", ".zsh", ".sql", ".r", ".m", ".lua", ".pl", ".ex", ".exs",
    ".hs", ".ml", ".clj", ".dart", ".v", ".zig",
})

CONFIG_EXTENSIONS = frozenset({
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml", ".csv",
    ".lock", ".conf",
})

PROSE_EXTENSIONS = frozenset({
    ".md", ".txt", ".rst", ".tex", ".adoc", ".org", ".html", ".htm", ".xhtml",
})

SENSITIVE_BASENAME_RE = re.compile(
    r"(?ix)^("
    r"\.env(\..+)?"
    r"|\.netrc"
    r"|credentials(\..+)?"
    r"|secrets?(\..+)?"
    r"|passwords?(\..+)?"
    r"|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?"
    r"|authorized_keys"
    r"|known_hosts"
    r"|.*\.(pem|key|p12|pfx|crt|cer|jks|keystore|asc|gpg)"
    r")$"
)

SENSITIVE_PATH_PARTS = frozenset({".ssh", ".aws", ".gnupg", ".kube", ".docker"})


@dataclass
class ContextItem:
    path: str
    content: str
    is_code: bool
    language: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


def is_sensitive(filepath: Path) -> bool:
    if SENSITIVE_BASENAME_RE.match(filepath.name):
        return True
    lowered = {p.lower() for p in filepath.parts}
    return bool(lowered & SENSITIVE_PATH_PARTS)


def classify_file(filepath: Path) -> tuple[bool, Optional[str]]:
    ext = filepath.suffix.lower()
    if ext in CODE_EXTENSIONS:
        return True, ext.lstrip(".")
    if ext in CONFIG_EXTENSIONS:
        return True, ext.lstrip(".")
    if ext in PROSE_EXTENSIONS:
        return False, None
    return True, None  # default to code (don't compress unknown)


def _html_to_text(content: str) -> str:
    # Remove script/style blocks first, then strip tags.
    cleaned = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", content, flags=re.IGNORECASE)
    cleaned = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def normalize_content(filepath: Path, content: str) -> str:
    if filepath.suffix.lower() in {".html", ".htm", ".xhtml"}:
        return _html_to_text(content)
    return content


async def collect_context(paths: list[str]) -> list[ContextItem]:
    items: list[ContextItem] = []
    for path_str in paths:
        path = Path(path_str).expanduser().resolve()

        if not path.exists():
            items.append(ContextItem(
                path=path_str, content="", is_code=False,
                warnings=[f"Path not found: {path_str}"],
            ))
            continue

        if path.is_file():
            item = _read_file(path)
            if item:
                items.append(item)
        elif path.is_dir():
            items.extend(_read_directory(path))

    return items


def _read_file(filepath: Path) -> Optional[ContextItem]:
    if is_sensitive(filepath):
        return ContextItem(
            path=str(filepath), content="", is_code=False,
            warnings=[f"Skipped sensitive file: {filepath.name}"],
        )

    size = filepath.stat().st_size
    if size > MAX_FILE_SIZE:
        return ContextItem(
            path=str(filepath), content="", is_code=False,
            warnings=[f"Skipped (>{MAX_FILE_SIZE // 1000}KB): {filepath.name}"],
        )

    try:
        content = filepath.read_text(errors="replace")
    except Exception as e:
        return ContextItem(
            path=str(filepath), content="", is_code=False,
            warnings=[f"Read error: {e}"],
        )

    content = normalize_content(filepath, content)
    is_code, language = classify_file(filepath)
    return ContextItem(
        path=str(filepath), content=content,
        is_code=is_code, language=language,
    )


def _read_directory(dirpath: Path, max_files: int = 50) -> list[ContextItem]:
    items = []
    count = 0
    for root, dirs, files in os.walk(dirpath):
        # Skip hidden and common non-useful directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in {
            "node_modules", "__pycache__", ".git", "venv", ".venv",
            "dist", "build", "target", ".next",
        }]
        for fname in sorted(files):
            if count >= max_files:
                items.append(ContextItem(
                    path=str(dirpath), content="", is_code=False,
                    warnings=[f"Directory truncated at {max_files} files"],
                ))
                return items
            fpath = Path(root) / fname
            item = _read_file(fpath)
            if item and item.content:
                items.append(item)
                count += 1
    return items
