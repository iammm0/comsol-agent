"""Model pricing — Python port of utils/modelCost.ts.

Pricing values mirror the upstream tiers exactly. The npm version logs an
analytics event on unknown models; here we just fall back to the
DEFAULT_UNKNOWN_MODEL_COST tier and let callers decide what to track.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelCosts:
    """USD per million input/output tokens (cache + web-search per request)."""

    input_tokens: float
    output_tokens: float
    prompt_cache_write_tokens: float
    prompt_cache_read_tokens: float
    web_search_requests: float


# Standard pricing tier for Sonnet models: $3 input / $15 output per Mtok
COST_TIER_3_15 = ModelCosts(
    input_tokens=3.0,
    output_tokens=15.0,
    prompt_cache_write_tokens=3.75,
    prompt_cache_read_tokens=0.3,
    web_search_requests=0.01,
)

# Pricing tier for Opus 4 / 4.1: $15 input / $75 output per Mtok
COST_TIER_15_75 = ModelCosts(
    input_tokens=15.0,
    output_tokens=75.0,
    prompt_cache_write_tokens=18.75,
    prompt_cache_read_tokens=1.5,
    web_search_requests=0.01,
)

# Pricing tier for Opus 4.5 (also default Opus 4.6): $5 input / $25 output per Mtok
COST_TIER_5_25 = ModelCosts(
    input_tokens=5.0,
    output_tokens=25.0,
    prompt_cache_write_tokens=6.25,
    prompt_cache_read_tokens=0.5,
    web_search_requests=0.01,
)

# Fast-mode pricing for Opus 4.6: $30 input / $150 output per Mtok
COST_TIER_30_150 = ModelCosts(
    input_tokens=30.0,
    output_tokens=150.0,
    prompt_cache_write_tokens=37.5,
    prompt_cache_read_tokens=3.0,
    web_search_requests=0.01,
)

# Pricing for Haiku 3.5: $0.80 input / $4 output per Mtok
COST_HAIKU_35 = ModelCosts(
    input_tokens=0.8,
    output_tokens=4.0,
    prompt_cache_write_tokens=1.0,
    prompt_cache_read_tokens=0.08,
    web_search_requests=0.01,
)

# Pricing for Haiku 4.5: $1 input / $5 output per Mtok
COST_HAIKU_45 = ModelCosts(
    input_tokens=1.0,
    output_tokens=5.0,
    prompt_cache_write_tokens=1.25,
    prompt_cache_read_tokens=0.1,
    web_search_requests=0.01,
)

DEFAULT_UNKNOWN_MODEL_COST = COST_TIER_5_25


# Canonical short-name → cost tier. Lookup uses substring matching so that
# version-suffixed model IDs (`claude-opus-4-6-20251015`) resolve correctly.
MODEL_COSTS: dict[str, ModelCosts] = {
    'claude-3-5-haiku': COST_HAIKU_35,
    'claude-haiku-4-5': COST_HAIKU_45,
    'claude-3-5-sonnet': COST_TIER_3_15,
    'claude-3-7-sonnet': COST_TIER_3_15,
    'claude-sonnet-4': COST_TIER_3_15,
    'claude-sonnet-4-5': COST_TIER_3_15,
    'claude-sonnet-4-6': COST_TIER_3_15,
    'claude-opus-4': COST_TIER_15_75,
    'claude-opus-4-1': COST_TIER_15_75,
    'claude-opus-4-5': COST_TIER_5_25,
    'claude-opus-4-6': COST_TIER_5_25,
}


def _resolve_model_costs(model: str) -> ModelCosts | None:
    """Return MODEL_COSTS entry for `model`, matching by longest prefix."""
    canonical = model.lower()
    matches = [
        (key, costs)
        for key, costs in MODEL_COSTS.items()
        if canonical.startswith(key) or key in canonical
    ]
    if not matches:
        return None
    # Prefer the most specific (longest) key match so `claude-opus-4-6` wins
    # over `claude-opus-4`.
    matches.sort(key=lambda item: len(item[0]), reverse=True)
    return matches[0][1]


def get_opus_4_6_cost_tier(fast_mode: bool) -> ModelCosts:
    """Return the right tier for Opus 4.6 — fast mode is more expensive."""
    return COST_TIER_30_150 if fast_mode else COST_TIER_5_25


def get_model_costs(model: str, *, fast_mode: bool = False) -> ModelCosts:
    """Return ModelCosts for `model`, applying the Opus 4.6 fast-mode tier."""
    canonical = model.lower()
    if 'claude-opus-4-6' in canonical:
        return get_opus_4_6_cost_tier(fast_mode)
    costs = _resolve_model_costs(model)
    return costs if costs is not None else DEFAULT_UNKNOWN_MODEL_COST


def tokens_to_usd_cost(
    costs: ModelCosts,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    web_search_requests: int = 0,
) -> float:
    """Compute USD cost from token counts and a ModelCosts tier."""
    return (
        (input_tokens / 1_000_000) * costs.input_tokens
        + (output_tokens / 1_000_000) * costs.output_tokens
        + (cache_read_input_tokens / 1_000_000) * costs.prompt_cache_read_tokens
        + (cache_creation_input_tokens / 1_000_000) * costs.prompt_cache_write_tokens
        + web_search_requests * costs.web_search_requests
    )


def calculate_usd_cost(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    web_search_requests: int = 0,
    fast_mode: bool = False,
) -> float:
    """USD cost for a query — looks up the tier and applies tokens_to_usd_cost."""
    costs = get_model_costs(model, fast_mode=fast_mode)
    return tokens_to_usd_cost(
        costs,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_creation_input_tokens=cache_creation_input_tokens,
        web_search_requests=web_search_requests,
    )


def calculate_cost_from_tokens(
    model: str,
    tokens: dict,
    *,
    fast_mode: bool = False,
) -> float:
    """Mirror calculateCostFromTokens — accepts the same camelCase token dict."""
    return calculate_usd_cost(
        model,
        input_tokens=int(tokens.get('inputTokens', 0)),
        output_tokens=int(tokens.get('outputTokens', 0)),
        cache_read_input_tokens=int(tokens.get('cacheReadInputTokens', 0)),
        cache_creation_input_tokens=int(tokens.get('cacheCreationInputTokens', 0)),
        web_search_requests=int(tokens.get('webSearchRequests', 0)),
        fast_mode=fast_mode,
    )


def _format_price(price: float) -> str:
    if float(price).is_integer():
        return f'${int(price)}'
    return f'${price:.2f}'


def format_model_pricing(costs: ModelCosts) -> str:
    """Return a human-readable pricing label like '$3/$15 per Mtok'."""
    return (
        f'{_format_price(costs.input_tokens)}/'
        f'{_format_price(costs.output_tokens)} per Mtok'
    )


def get_model_pricing_string(model: str) -> str | None:
    """Return formatted pricing string for `model`, or None if unknown."""
    costs = _resolve_model_costs(model)
    if costs is None:
        return None
    return format_model_pricing(costs)


__all__ = [
    'ModelCosts',
    'COST_TIER_3_15',
    'COST_TIER_15_75',
    'COST_TIER_5_25',
    'COST_TIER_30_150',
    'COST_HAIKU_35',
    'COST_HAIKU_45',
    'DEFAULT_UNKNOWN_MODEL_COST',
    'MODEL_COSTS',
    'get_opus_4_6_cost_tier',
    'get_model_costs',
    'tokens_to_usd_cost',
    'calculate_usd_cost',
    'calculate_cost_from_tokens',
    'format_model_pricing',
    'get_model_pricing_string',
]
