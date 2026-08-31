from __future__ import annotations

from miniagent.llm import complete
from miniagent.tools.dispatch import dispatch
from miniagent.tools.registry import all_tool_schemas
from miniagent.types import Message, AgentResult
from miniagent.cost import get_session_spend
import json

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
    history: list[Message] = [Message.user_text(task)]
    tools = all_tool_schemas()
    start_spend = get_session_spend()
    call_counts: dict[str, int] = {}      # signature -> times seen

    for step in range(max_steps):
        run_spend = get_session_spend() - start_spend
        if run_spend >= max_cost:
            return AgentResult(output=f"'{block.name}' repeated", stop_reason="max_cost",
                   steps=step + 1, cost=run_spend)

        resp = await complete(history, model=model, tools=tools, max_tokens=max_tokens,system=DEFAULT_SYSTEM)
        history.append(resp.to_message())

        if resp.stop_reason != "tool_use":
            text_blocks = [b.text for b in resp.content if b.type == "text"]
            run_spend = get_session_spend() - start_spend 
            return AgentResult(output="\n".join(text_blocks), stop_reason="completed",
                   steps=step + 1, cost=run_spend)

        # LOOP DETECTION — check each requested call's signature
        for block in resp.tool_uses:
            sig = _call_signature(block)
            call_counts[sig] = call_counts.get(sig, 0) + 1
            if call_counts[sig] >= max_repeats:
                return AgentResult(output=f"'{block.name}' repeated", stop_reason="loop_detected",
                   steps=step + 1, cost=run_spend)

        results = [dispatch(block) for block in resp.tool_uses]
        history.append(Message(role="user", content=results))
        run_spend = get_session_spend() - start_spend 
        print(f"[agent] step {step + 1}/{max_steps}, spent ${run_spend:.4f}")

    return AgentResult(output=f"'{block.name}' repeated", stop_reason="max_steps",
                   steps=step + 1, cost=run_spend)