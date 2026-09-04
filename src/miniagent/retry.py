from __future__ import annotations

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from miniagent.errors import LLMError


def _is_retryable(exc: BaseException) -> bool:
    # only retry errors WE marked retryable on Day 1 (429, 529, timeouts, connection)
    return isinstance(exc, LLMError) and exc.retryable


llm_retry = retry(
    retry=retry_if_exception(_is_retryable),      # which errors to retry
    stop=stop_after_attempt(4),                   # try at most 4 times
    wait=wait_exponential_jitter(initial=1, max=20),  # 1s, ~2s, ~4s... + jitter, capped
    reraise=False,                                 # on final failure, raise the real error
)