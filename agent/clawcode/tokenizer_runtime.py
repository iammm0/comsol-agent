from __future__ import annotations

import math
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable


@dataclass(frozen=True)
class TokenCounterInfo:
    backend: str
    source: str
    accurate: bool


@dataclass(frozen=True)
class ResolvedTokenCounter:
    info: TokenCounterInfo
    count_text: Callable[[str], int]


def count_tokens(text: str, model: str | None = None) -> int:
    counter = resolve_token_counter(model)
    return counter.count_text(text)


def describe_token_counter(model: str | None = None) -> TokenCounterInfo:
    return resolve_token_counter(model).info


def resolve_token_counter(model: str | None = None) -> ResolvedTokenCounter:
    return _resolve_token_counter(
        _normalize_model(model),
        _normalize_env('CLAW_CODE_TOKENIZER_PATH'),
        _normalize_env('CLAW_CODE_TOKENIZER_MODEL'),
        _normalize_env('CLAW_CODE_TOKENIZER_TRUST_REMOTE_CODE'),
    )


def clear_token_counter_cache() -> None:
    _resolve_token_counter.cache_clear()


@lru_cache(maxsize=64)
def _resolve_token_counter(
    normalized_model: str | None,
    explicit_path: str | None,
    explicit_model: str | None,
    trust_remote_code: str | None,
) -> ResolvedTokenCounter:
    transformer_ref = explicit_path or explicit_model or normalized_model

    if _prefer_tiktoken(normalized_model):
        counter = _try_build_tiktoken_counter(normalized_model)
        if counter is not None:
            return counter
        counter = _try_build_transformers_counter(transformer_ref, trust_remote_code)
        if counter is not None:
            return counter
    else:
        counter = _try_build_transformers_counter(transformer_ref, trust_remote_code)
        if counter is not None:
            return counter
        counter = _try_build_tiktoken_counter(normalized_model)
        if counter is not None:
            return counter

    return ResolvedTokenCounter(
        info=TokenCounterInfo(
            backend='heuristic',
            source='len(text)/4 fallback',
            accurate=False,
        ),
        count_text=_heuristic_count,
    )


def _normalize_model(model: str | None) -> str | None:
    if not isinstance(model, str):
        return None
    normalized = model.strip()
    return normalized or None


def _normalize_env(name: str) -> str | None:
    value = os.environ.get(name)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _prefer_tiktoken(model: str | None) -> bool:
    if model is None:
        return False
    lowered = model.lower()
    return (
        lowered.startswith('gpt')
        or lowered.startswith('o1')
        or lowered.startswith('o3')
        or lowered.startswith('o4')
        or 'gpt-4' in lowered
        or 'gpt-5' in lowered
        or 'openai' in lowered
    )


def _try_build_tiktoken_counter(model: str | None) -> ResolvedTokenCounter | None:
    if model is None:
        return None
    try:
        import tiktoken
    except ImportError:
        return None

    encoding = None
    encoding_name = None
    try:
        encoding = tiktoken.encoding_for_model(model)
        encoding_name = getattr(encoding, 'name', model)
    except KeyError:
        fallback_name = _tiktoken_fallback_encoding(model)
        if fallback_name is None:
            return None
        encoding = tiktoken.get_encoding(fallback_name)
        encoding_name = fallback_name
    except Exception:
        return None

    def _count(text: str) -> int:
        if not text:
            return 0
        return len(encoding.encode_ordinary(text))

    return ResolvedTokenCounter(
        info=TokenCounterInfo(
            backend='tiktoken',
            source=encoding_name or 'unknown',
            accurate=True,
        ),
        count_text=_count,
    )


def _tiktoken_fallback_encoding(model: str) -> str | None:
    lowered = model.lower()
    if lowered.startswith('gpt') or lowered.startswith('o1') or lowered.startswith('o3') or lowered.startswith('o4'):
        return 'o200k_base'
    if 'gpt-3.5' in lowered or 'gpt-4' in lowered:
        return 'cl100k_base'
    return None


def _try_build_transformers_counter(
    model_ref: str | None,
    trust_remote_code: str | None,
) -> ResolvedTokenCounter | None:
    if model_ref is None or not _should_try_transformers(model_ref):
        return None
    try:
        from transformers import AutoTokenizer
    except ImportError:
        return None

    trust_remote_code_enabled = isinstance(trust_remote_code, str) and trust_remote_code.lower() in {
        '1',
        'true',
        'yes',
        'on',
    }
    tokenizer = None
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_ref,
            local_files_only=True,
            use_fast=True,
            trust_remote_code=trust_remote_code_enabled,
        )
    except Exception:
        return None

    def _count(text: str) -> int:
        if not text:
            return 0
        encoded: Any = tokenizer.encode(text, add_special_tokens=False)
        return len(encoded)

    return ResolvedTokenCounter(
        info=TokenCounterInfo(
            backend='transformers',
            source=f'{model_ref} (local_files_only)',
            accurate=True,
        ),
        count_text=_count,
    )


def _should_try_transformers(model_ref: str) -> bool:
    if os.path.exists(model_ref):
        return True
    normalized = model_ref.strip()
    if not normalized:
        return False
    return '/' in normalized or '\\' in normalized


def _heuristic_count(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))
