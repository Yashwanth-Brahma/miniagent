from __future__ import annotations
from miniagent.types import ContentBlock
from pydantic import TypeAdapter, json
from miniagent.trace import log_call

import asyncio
import time
from typing import Any

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from miniagent.errors import LLMError
from miniagent.types import Message, Response, StopReason, Usage, TextBlock, ToolUseBlock

from dotenv import load_dotenv
load_dotenv()

_blocks_adapter = TypeAdapter(list[ContentBlock])

_anthropic = AsyncAnthropic()
_openai = AsyncOpenAI()

_STOP_MAP: dict[str, StopReason] = {
    "end_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "stop_sequence": "stop_sequence",
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "other",
}


def _map_stop_reason(raw: str | None) -> StopReason:
    if raw is None:
        return "other"
    return _STOP_MAP.get(raw, "other")

def _provider_of(model: str) -> str:
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    return "unknown"

async def complete(
    messages: list[Message],
    *,
    model: str,
    system: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 4096,
    temperature: float = 1.0,
) -> Response:
    start = time.perf_counter()
    response: Response | None = None
    error: Exception | None = None
    try:
        if model.startswith("claude"):
            response = await _complete_anthropic(
                messages, model=model, system=system, tools=tools,
                max_tokens=max_tokens, temperature=temperature,
            )
        elif model.startswith(("gpt", "o1", "o3", "o4")):
            response = await _complete_openai(
                messages, model=model, system=system, tools=tools,
                max_tokens=max_tokens, temperature=temperature,
            )
        else:
            raise ValueError(f"Unknown model: {model}")
        return response
    except Exception as e:
        error = e
        raise
    finally:
        log_call(
            provider=_provider_of(model),
            model=model,
            request={
                "messages": [m.model_dump() for m in messages],
                "system": system,
                "tools": tools,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            response=response.model_dump() if response else None,
            error=repr(error) if error else None,
            latency_ms=(time.perf_counter() - start) * 1000,
        )

def _to_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    return [m.model_dump() for m in messages]


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    return [m.model_dump() for m in messages]


async def _complete_anthropic(
    messages: list[Message],
    *,
    model: str,
    system: str | None,
    tools: list[dict[str, Any]] | None,
    max_tokens: int,
    temperature: float,
) -> Response:
    anthropic_messages = _to_anthropic_messages(messages)

    try:
        resp = await _anthropic.messages.create(
            model=model,
            messages=anthropic_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as e:
        raise LLMError(str(e), retryable=True) from e
    return Response(
        content=_blocks_adapter.validate_python(
            [b.model_dump() for b in resp.content]),
        stop_reason=_map_stop_reason(resp.stop_reason),
        usage=Usage(
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
        ),
        model=model,
        raw=resp.model_dump(),
    )


async def _complete_openai(
    messages: list[Message],
    *,
    model: str,
    system: str | None,
    tools: list[dict[str, Any]] | None,
    max_tokens: int,
    temperature: float,
) -> Response:
    openai_messages = _to_openai_messages(messages)
    try:
        resp = await _openai.chat.completions.create(
            model=model,
            messages=openai_messages,
            max_completion_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception as e:
        raise LLMError(str(e), retryable=True) from e

    msg = resp.choices[0].message
    blocks: list[ContentBlock] = []

    if msg.content:                        # str, and not None/empty
        blocks.append(TextBlock(text=msg.content))

    for call in msg.tool_calls or []:      # None-safe
        blocks.append(ToolUseBlock(
            id=call.id,
            name=call.function.name,
            # arguments is a JSON *string*
            input=json.loads(call.function.arguments),
        ))

    return Response(
        content=blocks,
        stop_reason=_map_stop_reason(resp.choices[0].finish_reason),
        usage=Usage(
            input_tokens=resp.usage.prompt_tokens,
            output_tokens=resp.usage.completion_tokens,
        ),
        model=model,
        raw=resp.model_dump(),
    )


async def main():
    try:
        r = await complete([Message.user_text("Say hi in 3 words")], model="gpt-5.6-luna", max_tokens=50)
        assert r.stop_reason == "end_turn"
        print(r.content[0], TextBlock)
        print(r.stop_reason, r.usage.input_tokens, r.usage.output_tokens)
    except Exception as e:
        print(f"Error occurred: {e}")
        pass

asyncio.run(main())
