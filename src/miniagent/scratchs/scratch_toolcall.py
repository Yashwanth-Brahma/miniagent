# scratch_toolcall.py
import asyncio

from miniagent.llm import complete
from miniagent.tools.dispatch import dispatch
from miniagent.tools.registry import all_tool_schemas
import miniagent.tools.registry  # side-effect import: registers read_file
# from miniagent.models import FAST
from miniagent.types import Message, ToolUseBlock


async def main() -> None:
    tools = all_tool_schemas()

    # a question that REQUIRES reading the file to answer
    history = [Message.user_text("What files are in the current directory?")]
    # ---- CALL 1: model decides to use a tool ----
    resp1 = await complete(history, model="claude-haiku-4-5-20251001", tools=tools, max_tokens=1024)
    print("call 1 stop_reason:", resp1.stop_reason)          # expect: tool_use
    print("call 1 tool_uses:", [b.name for b in resp1.tool_uses])

    # add the assistant's turn (with its tool_use blocks) to history
    history.append(resp1.to_message())

    # ---- YOUR CODE: run each requested tool ----
    tool_results = []
    for block in resp1.tool_uses:
        result = dispatch(block)
        print(f"  ran {block.name}({block.input}) -> is_error={result.is_error}")
        tool_results.append(result)

    # send the results back as a single user message
    history.append(Message(role="user", content=tool_results))

    # ---- CALL 2: model reads the results and answers ----
    resp2 = await complete(history, model="claude-haiku-4-5-20251001", tools=tools, max_tokens=1024)
    print("call 2 stop_reason:", resp2.stop_reason)          # expect: end_turn
    print("final answer:", resp2.content[0].text)


asyncio.run(main())