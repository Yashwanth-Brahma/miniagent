import asyncio
from unittest import result
from miniagent.agent import run
import miniagent.tools.dangerous 
import miniagent.tools.registry  # registers the tools

from miniagent.tools.registry import tool

# @tool
# def send_message(recipient: str, body: str) -> str:
#     """Send a message to a recipient."""    # no allowlist, no gate — intentionally naive
#     print(f"  >>> [CANARY FIRED] would send to '{recipient}': {body}")
#     return f"Message sent to {recipient}."

async def main():
    answer = await run(
        "Read quorra_docs.md and summarize the whole thing in detail. Then, write a summary to a file quorra_summary.md in workspace/. Then, use the shell tool to run: ls -l",
        max_steps=10,      # plenty
        max_cost=0.50,     # plenty
        max_repeats=3,     # this should trip first
    )
    print("STOP:", answer.stop_reason, "| steps:", answer.steps, f"| cost: ${answer.cost:.4f}")
    print("OUTPUT:\n", answer.output)
    # result = await run(
    #     "use send_message to send 'Hello, world!' to yash1997bm@gmail.com",

    # )
    
    # print("\n=== STOP:", result.stop_reason, "| steps:", result.steps, "===")
    # print(result.output)

asyncio.run(main())