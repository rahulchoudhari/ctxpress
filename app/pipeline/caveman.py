"""
Rule-based text compression inspired by caveman (JuliusBrussee/caveman).
Purely programmatic - no LLM calls. Protects code/URLs/paths, compresses prose.
"""

import re
from dataclasses import dataclass

# --- Protected segment patterns (never modified) ---

PROTECTED_PATTERNS = [
    re.compile(r"```[\s\S]*?```"),                          # fenced code blocks
    re.compile(r"`[^`\n]+`"),                               # inline code
    re.compile(r"https?://\S+"),                            # URLs
    re.compile(r"(?<!\w)[./~][\w./\-]+(?:\.\w+)+"),         # file paths with extension
    re.compile(r"\bv?\d+\.\d+(?:\.\d+)*\b"),                # version numbers
    re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b"),                  # CONST_CASE
]

# --- Filler / redundancy word lists ---

FILLER_WORDS = [
    "just", "really", "basically", "actually", "simply", "quite",
    "very", "essentially", "literally", "definitely", "certainly",
    "obviously", "clearly", "honestly", "frankly", "indeed",
]

HEDGING_PHRASES = [
    "perhaps", "maybe", "it seems like", "it appears that",
    "I think", "in my opinion", "I believe", "I would say",
    "it might be", "could potentially", "might want to",
    "you may want to consider",
]

PLEASANTRIES = [
    r"I'd be happy to help[.!]?\s*",
    r"Sure[!,]\s*",
    r"Certainly[!,]\s*",
    r"Of course[!,]\s*",
    r"Great question[!,]\s*",
    r"That's a great question[!,]\s*",
    r"Let me explain[.:]\s*",
    r"I'll help you with that[.!]?\s*",
    r"Happy to help[!,]?\s*",
    r"No problem[!,]\s*",
    r"Absolutely[!,]\s*",
]

REDUNDANT_PHRASES = {
    "in order to": "to",
    "due to the fact that": "because",
    "at this point in time": "now",
    "a large number of": "many",
    "in the event that": "if",
    "is able to": "can",
    "has the ability to": "can",
    "for the purpose of": "to",
    "with regard to": "about",
    "with respect to": "about",
    "in addition to": "also",
    "as a result of": "from",
    "on the other hand": "but",
    "in spite of": "despite",
    "take into account": "consider",
    "the fact that": "that",
    "it is important to note that": "note:",
    "it is worth noting that": "note:",
    "keep in mind that": "note:",
    "make sure to": "",
    "be sure to": "",
    "you will need to": "",
    "you would need to": "",
    "what this means is": "",
    "what this does is": "",
}

# Articles pattern (only before lowercase words)
ARTICLE_RE = re.compile(r"\b(a|an|the)\s+(?=[a-z])", re.IGNORECASE)

LEADING_PHRASES = [
    r"^I'll\s+",
    r"^You can\s+",
    r"^We will\s+",
    r"^Let me\s+",
    r"^You should\s+",
    r"^You need to\s+",
    r"^It's worth noting that\s+",
    r"^As mentioned earlier,?\s+",
    r"^As I mentioned,?\s+",
    r"^To do this,?\s+",
    r"^In this case,?\s+",
    r"^First of all,?\s+",
    r"^At the end of the day,?\s+",
]

ABBREVIATIONS = {
    "database": "DB",
    "databases": "DBs",
    "authentication": "auth",
    "authorization": "authz",
    "configuration": "config",
    "configurations": "configs",
    "request": "req",
    "requests": "reqs",
    "response": "res",
    "responses": "ress",
    "repository": "repo",
    "repositories": "repos",
    "development": "dev",
    "production": "prod",
    "environment": "env",
    "environments": "envs",
    "application": "app",
    "applications": "apps",
    "information": "info",
    "documentation": "docs",
    "function": "fn",
    "functions": "fns",
    "parameter": "param",
    "parameters": "params",
    "directory": "dir",
    "directories": "dirs",
    "dependency": "dep",
    "dependencies": "deps",
    "implementation": "impl",
    "specifications": "specs",
    "specification": "spec",
    "approximately": "~",
    "administrator": "admin",
    "administrators": "admins",
}

CAUSALITY_PHRASES = {
    "leads to": "->",
    "results in": "->",
    "which causes": "->",
    "which leads to": "->",
    "this means": "->",
    "therefore": "->",
    "consequently": "->",
    "as a result": "->",
}


@dataclass
class CompressionResult:
    text: str
    original_chars: int
    compressed_chars: int


def _protect_segments(text: str) -> tuple[str, list[str]]:
    """Extract protected segments, replace with placeholders."""
    segments: list[str] = []

    def _replace(match: re.Match) -> str:
        idx = len(segments)
        segments.append(match.group(0))
        return f"\x00PROT{idx}\x00"

    for pattern in PROTECTED_PATTERNS:
        text = pattern.sub(_replace, text)

    return text, segments


def _restore_segments(text: str, segments: list[str]) -> str:
    """Restore protected segments from placeholders."""
    for idx, segment in enumerate(segments):
        text = text.replace(f"\x00PROT{idx}\x00", segment)
    return text


def _apply_lite(text: str) -> str:
    """Remove filler, hedging, pleasantries, redundant phrases."""
    # Pleasantries (full phrases)
    for pattern in PLEASANTRIES:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Hedging phrases
    for phrase in HEDGING_PHRASES:
        text = re.sub(r"\b" + re.escape(phrase) + r"\b,?\s*", "", text, flags=re.IGNORECASE)

    # Filler words (standalone, not part of larger words)
    for word in FILLER_WORDS:
        text = re.sub(r"\b" + re.escape(word) + r"\b\s*", "", text, flags=re.IGNORECASE)

    # Redundant phrases
    for phrase, replacement in REDUNDANT_PHRASES.items():
        text = re.sub(re.escape(phrase), replacement, text, flags=re.IGNORECASE)

    return text


def _apply_full(text: str) -> str:
    """Remove articles and leading phrases (includes lite)."""
    text = _apply_lite(text)

    # Remove articles before lowercase words
    text = ARTICLE_RE.sub("", text)

    # Remove leading phrases (per line)
    lines = text.split("\n")
    processed = []
    for line in lines:
        stripped = line.strip()
        for pattern in LEADING_PHRASES:
            stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)
        processed.append(stripped)
    text = "\n".join(processed)

    return text


def _apply_ultra(text: str) -> str:
    """Abbreviate common words and use arrows (includes full)."""
    text = _apply_full(text)

    # Abbreviations (case-insensitive, word boundaries)
    for word, abbr in ABBREVIATIONS.items():
        text = re.sub(r"\b" + re.escape(word) + r"\b", abbr, text, flags=re.IGNORECASE)

    # Causality arrows
    for phrase, arrow in CAUSALITY_PHRASES.items():
        text = re.sub(re.escape(phrase), arrow, text, flags=re.IGNORECASE)

    return text


def _post_process(text: str) -> str:
    """Clean up whitespace artifacts from transformations."""
    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)
    # Remove space before punctuation
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    # Collapse 3+ newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip leading/trailing whitespace per line
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    # Strip overall
    text = text.strip()
    return text


def compress(text: str, level: str = "full", is_code: bool = False) -> CompressionResult:
    """Compress text using caveman rules. Code is never modified."""
    original_chars = len(text)

    if is_code or not text.strip():
        return CompressionResult(text=text, original_chars=original_chars, compressed_chars=original_chars)

    # Protect code/URLs/paths
    working, segments = _protect_segments(text)

    # Apply compression level
    if level == "lite":
        working = _apply_lite(working)
    elif level == "ultra":
        working = _apply_ultra(working)
    else:
        working = _apply_full(working)

    # Post-process whitespace
    working = _post_process(working)

    # Restore protected segments
    result = _restore_segments(working, segments)

    return CompressionResult(
        text=result,
        original_chars=original_chars,
        compressed_chars=len(result),
    )


def compress_context(items: list, level: str = "full") -> list:
    """Apply caveman compression to context items (prose only)."""
    from .context import ContextItem

    results = []
    for item in items:
        if item.is_code or not item.content:
            results.append(item)
            continue

        result = compress(item.content, level=level)
        results.append(ContextItem(
            path=item.path,
            content=result.text,
            is_code=item.is_code,
            language=item.language,
            warnings=item.warnings,
        ))
    return results
