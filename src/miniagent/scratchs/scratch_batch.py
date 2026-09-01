import asyncio
from miniagent.agent import run
from miniagent.metrics import report
import miniagent.tools.dangerous
import miniagent.tools.registry

TASKS = [
    "Read quorra_docs.md and summarize backpressure in one sentence.",
    "What files are in the workspace? Use list_dir.",
    "Read quorra_docs.md and list the three storage guarantees.",
    "Use sql_query to show all users.",
    "Read quorra_docs.md and explain the write-before-proceed rule.",
    "What does the authentication section say about credential rotation?",
]

async def main():
    for t in TASKS:
        r = await run(t, max_steps=6)
        print(f"  [{r.stop_reason}] {r.steps} steps, ${r.cost:.4f}  — {t[:40]}")
    print("\n=== METRICS ===")
    report()

asyncio.run(main())