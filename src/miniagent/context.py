from __future__ import annotations

from miniagent.types import Message
from miniagent.tokens import count_tokens_openai

def _truncate_oldest(messages, max_tokens, model):
    """
    Truncate the oldest messages until the total token count is within the max_tokens limit.
    Args:
        messages (list[Message]): The list of messages to truncate.
        max_tokens (int): The maximum allowed token count.
        model (str): The model name to use for tokenization.
    Returns:
        list[Message]: The truncated list of messages that fits within the token limit.
    """
    result = list(messages)
    while count_tokens_openai(result, model) > max_tokens and len(result) > 1:
        result.pop(0)  # remove the oldest
    return result

def _sliding_window(messages, max_tokens, model):
    """
    Use a sliding window approach to fit messages within the token limit.
    Args:
        messages (list[Message]): The list of messages to fit.
        max_tokens (int): The maximum allowed token count.
        model (str): The model name to use for tokenization.
    Returns:
        list[Message]: The list of messages that fits within the token limit.
    """
    if not messages:
        return []
    pinned = messages[0]          # the task — never drop this
    rest = list(messages[1:])
    while count_tokens_openai([pinned, *rest], model) > max_tokens and rest:
        rest.pop(0)               # drop oldest of the *rest*
    return [pinned, *rest]

def _summarize_middle(messages, max_tokens, model):
    """
    Summarize the middle messages to fit within the token limit.
    Args:
        messages (list[Message]): The list of messages to summarize.
        max_tokens (int): The maximum allowed token count.
        model (str): The model name to use for tokenization.
    Returns:
        list[Message]: The list of messages that fits within the token limit.
    """
    if len(messages) <= 4:
        return list(messages)
    first = messages[0]
    last_two = messages[-2:]
    # STUB: real version calls the LLM to summarize the dropped middle.
    # For now, just a placeholder marker.
    summary = Message.user_text("[earlier conversation summarized — TODO: real LLM summary]")
    return [first, summary, *last_two]

def fit_to_budget(messages, *, max_tokens, model, strategy="sliding_window"):
    if strategy == "truncate_oldest":
        return _truncate_oldest(messages, max_tokens, model)
    if strategy == "sliding_window":
        return _sliding_window(messages, max_tokens, model)
    if strategy == "summarize_middle":
        return _summarize_middle(messages, max_tokens, model)
    raise ValueError(f"Unknown strategy: {strategy}")