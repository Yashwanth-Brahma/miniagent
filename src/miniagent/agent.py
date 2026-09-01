from __future__ import annotations

from miniagent.llm import complete
from miniagent.tools.dispatch import dispatch
from miniagent.tools.registry import REGISTRY, all_tool_schemas
from miniagent.types import Message, AgentResult, ToolResultBlock
from miniagent.cost import get_session_spend, estimate_cost
import json
import time
import uuid
from miniagent.spans import Span, write_span

DEFAULT_SYSTEM = """You are a coding and research assistant with access to tools.
- Use tools to gather real information rather than guessing.
- When you have enough information to answer, respond directly without more tool calls.
- If a tool fails repeatedly, stop and report the problem instead of retrying endlessly.
- Be concise."""

def _call_signature(block) -> str:
    # name + sorted args = a stable fingerprint of "what this call is"
    return f"{block.name}:{json.dumps(block.input, sort_keys=True)}"

async def run(
    task: str,
    *,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 2048,
    max_steps: int = 10,
    max_cost: float = 0.50,
    max_repeats: int = 3,          # <-- same call this many times = stuck
) -> str:
    run_id = str(uuid.uuid4())[:8]        # one id for this whole run
    history: list[Message] = [Message.user_text(task)]
    tools = all_tool_schemas()
    start_spend = get_session_spend()
    call_counts: dict[str, int] = {}      # signature -> times seen

    for step in range(max_steps):
        run_spend = get_session_spend() - start_spend
        if run_spend >= max_cost:
            return AgentResult(output=f"'{block.name}' repeated", stop_reason="max_cost",
                   steps=step + 1, cost=run_spend)

        step_start = time.perf_counter()
        resp = await complete(history, model=model, tools=tools, max_tokens=max_tokens,system=DEFAULT_SYSTEM)
        step_latency = (time.perf_counter() - step_start) * 1000

        history.append(resp.to_message())

        # record the span for this step
        write_span(Span(
            run_id=run_id,
            step=step + 1,
            latency_ms=step_latency,
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
            cost=estimate_cost(model, resp.usage),
            tool_calls=[b.name for b in resp.tool_uses],
            stop_reason=resp.stop_reason,
        ))


        if resp.stop_reason != "tool_use":
            text_blocks = [b.text for b in resp.content if b.type == "text"]
            run_spend = get_session_spend() - start_spend 
            return AgentResult(output="\n".join(text_blocks), stop_reason="completed",
                   steps=step + 1, cost=run_spend)

        # LOOP DETECTION — check each requested call's signature
        results = []
        for block in resp.tool_uses:
            sig = _call_signature(block)
            call_counts[sig] = call_counts.get(sig, 0) + 1
            if call_counts[sig] >= max_repeats:
                return (f"[stopped: '{block.name}' called with identical args "
                        f"{max_repeats} times — agent appears stuck]")
            
            fn = REGISTRY.get(block.name)
            if fn is not None and getattr(fn, "requires_approval", False):
                # PAUSE and ask the human
                print(f"\n⚠  The agent wants to call: {block.name}")
                print(f"   with arguments: {block.input}")
                answer = input("   Approve? [y/N] ").strip().lower()
                if answer != "y":
                    results.append(ToolResultBlock(
                        tool_use_id=block.id,
                        content="User denied permission to run this tool.",
                        is_error=True,
                    ))
                    continue
            results.append(dispatch(block))
        history.append(Message(role="user", content=results))
        run_spend = get_session_spend() - start_spend 
        print(f"[agent] step {step + 1}/{max_steps}, spent ${run_spend:.4f}, stop_reason={resp.stop_reason}, tool_name={block.name}, ")

    return AgentResult(output=f"'{block.name}' repeated", stop_reason="max_steps",
                   steps=step + 1, cost=run_spend)

