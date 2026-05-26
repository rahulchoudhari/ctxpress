import tiktoken

_encoder = None


def get_encoder():
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("o200k_base")
    return _encoder


def count_tokens(text: str) -> int:
    return len(get_encoder().encode(text))
