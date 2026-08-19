from __future__ import annotations

from miniagent.types import Usage

# Prices are USD per 1,000,000 tokens: (input_rate, output_rate).
# VERIFY these against the current pricing pages — they change, and mine may be stale.
PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001":  (1.00, 5.00),   # <- look up, don't trust me
    "gpt-4o-mini":      (0.15, 0.60),   # <- look up
}

def estimate_cost(model: str, usage: Usage) -> float:
    """
    Estimate the cost of a response based on the model and usage. Usage includes the number of input and output tokens, and the model determines the pricing rates. The cost is calculated as:
    cost = (input_tokens / 1,000,000) * input_rate + (output_tokens / 1,000,000) * output_rate
    where input_rate and output_rate are the rates for the specified model, in USD per 1,000,000 tokens.
    Args:
        model (str): The model name to use for pricing.
        usage (Usage): The usage object containing input and output token counts.
    Returns:
        float: The estimated cost in USD.
    """
    if model not in PRICING:
        return 0.0  # unknown model — don't crash, just report zero
    input_rate, output_rate = PRICING[model]
    input_cost = (usage.input_tokens / 1_000_000) * input_rate
    output_cost = (usage.output_tokens / 1_000_000) * output_rate
    return input_cost + output_cost

_session_spend: float = 0.0

def record_spend(model: str, usage: Usage) -> float:
    global _session_spend # Use the global variable to track session spend
    cost = estimate_cost(model, usage)
    _session_spend += cost
    return cost


def get_session_spend() -> float:
    return _session_spend
