from __future__ import annotations
from miniagent.llm import complete
from miniagent.agent import run, DEFAULT_SYSTEM
from miniagent.types import Message, TextBlock


async def summarize_messages(messages: list[Message], *, model: str) -> str:
    """Compress a run of messages into a short summary that preserves what matters."""
    # flatten the messages into readable text for the summarizer
    transcript = []
    for m in messages:
        text = " ".join(b.text for b in m.content if b.type == "text")
        tool_calls = [b.name for b in m.content if b.type == "tool_use"]
        if text:
            transcript.append(f"{m.role}: {text}")
        if tool_calls:
            transcript.append(f"{m.role} called tools: {', '.join(tool_calls)}")
    joined = "\n".join(transcript)

    prompt = (
        "Summarize this portion of an agent conversation in 2-3 sentences. "
        "Preserve: what the user wanted, key decisions or findings, and any facts "
        "the agent will need later. Drop pleasantries and redundancy.\n\n"
        f"{joined}"
    )
    resp = await complete([Message.user_text(prompt)], model=model, max_tokens=300)
    return " ".join(b.text for b in resp.content if b.type == "text")

async def summarize_middle(messages, *, model, keep_recent=4):
    if len(messages) <= keep_recent + 1:
        return messages
    first = messages[0]                          # pinned task (Day 2 lesson)
    middle = messages[1:-keep_recent]
    recent = messages[-keep_recent:]
    summary_text = await summarize_messages(middle, model=model)
    summary_msg = Message.user_text(f"[Summary of earlier conversation: {summary_text}]")
    return [first, summary_msg, *recent]

async def run_with_memory(task, mem, *, model):
    recalled = mem.recall(task, k=3)
    print(f"Recalled {len(recalled)} facts from memory for task: {task}")
    memory_block = ""
    if recalled:
        memory_block = "Relevant facts from earlier:\n" + "\n".join(f"- {f}" for f in recalled)

    system = f"{DEFAULT_SYSTEM}\n\n{memory_block}" if memory_block else DEFAULT_SYSTEM
    return await run(task, model=model, system=system)