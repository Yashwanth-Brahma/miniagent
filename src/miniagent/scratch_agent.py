import asyncio
from unittest import result
from miniagent.agent import run

import miniagent.tools.registry  # registers the tools


async def main():
    answer = await run(
        "Read quorra_docs.md and summarize the whole thing in detail.",
        max_steps=10,      # plenty
        max_cost=0.50,     # plenty
        max_repeats=3,     # this should trip first
    )
    print("STOP:", answer.stop_reason, "| steps:", answer.steps, f"| cost: ${answer.cost:.4f}")
    print("OUTPUT:\n", answer.output)

asyncio.run(main())