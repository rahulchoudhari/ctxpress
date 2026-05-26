import re

from .tokencount import count_tokens


INTENT_RULES = [
    (re.compile(r"\b(debug|fix|error|failing|traceback|exception|bug)\b", re.IGNORECASE), "debug"),
    (re.compile(r"\b(summarize|summary|tldr|brief|short)\b", re.IGNORECASE), "summarize"),
    (re.compile(r"\b(compare|difference|vs\.?|versus)\b", re.IGNORECASE), "compare"),
    (re.compile(r"\b(generate|create|write|draft|implement|build)\b", re.IGNORECASE), "generate"),
    (re.compile(r"\b(explain|why|how|what)\b", re.IGNORECASE), "explain"),
]


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\t+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _detect_intent(text: str) -> str:
    for pattern, intent in INTENT_RULES:
        if pattern.search(text):
            return intent
    return "general"


def _response_contract(intent: str, original: str) -> str:
    lowered = original.lower()

    prefers_bullets = any(k in lowered for k in ["bullet", "bullets", "list"])
    prefers_json = "json" in lowered
    prefers_table = "table" in lowered

    if prefers_json:
        return "Return valid JSON only."
    if prefers_table:
        return "Return a concise markdown table."

    if intent == "debug":
        contract = "Return: root cause, fix, and validation steps."
    elif intent == "summarize":
        contract = "Return a concise summary with key points only."
    elif intent == "compare":
        contract = "Return the main differences and a recommendation."
    elif intent == "generate":
        contract = "Return a direct, runnable result with minimal explanation."
    elif intent == "explain":
        contract = "Return a clear explanation and practical next step."
    else:
        contract = "Return a concise, direct answer."

    if prefers_bullets:
        return contract + " Use bullet points."
    return contract


def optimize_user_prompt(text: str) -> tuple[str, dict]:
    original = text or ""
    normalized = _normalize_text(original)
    intent = _detect_intent(normalized)
    contract = _response_contract(intent, normalized)

    # Keep user intent intact while adding a lightweight output contract.
    optimized = normalized
    if contract and contract.lower() not in normalized.lower():
        optimized = f"{normalized}\n\nOutput requirements: {contract}"

    stats = {
        "intent": intent,
        "original_tokens": count_tokens(original),
        "optimized_tokens": count_tokens(optimized),
    }
    stats["tokens_delta"] = stats["optimized_tokens"] - stats["original_tokens"]

    return optimized, stats
