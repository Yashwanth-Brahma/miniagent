# scratch_schema_experiment.py
import asyncio

from miniagent.llm import complete
from miniagent.types import Message


def make_schema(severity_desc: str) -> dict:
    return {
        "name": "search_events",
        "description": "Search system event log records.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Text to search for in event messages"},
                "severity": {"type": "string", "description": severity_desc},
            },
            "required": ["query", "severity"],
        },
    }


VARIANTS = {
    "terse": make_schema("the severity"),
    "detailed": make_schema(
        "Severity level to filter by. Must be exactly one of: debug, info, warn, error"
    ),
    "examples": make_schema(
        "Severity level to filter by. Must be exactly one of: debug, info, warn, error. "
        "Example: to find error messages use severity='error'; "
        "for warnings use severity='warn'."
    ),
}

# each prompt + the value the tool actually expects
CASES = [
    ("Find the error messages about database connections", "error"),
    ("What warnings came up during startup?",              "warn"),
    ("Show me debug output for the auth module",           "debug"),
    ("List the informational events from today",           "info"),
    ("Are there any errors related to payments?",          "error"),
    ("Any warnings about low disk space?",                 "warn"),
]


async def run_variant(name: str, schema: dict) -> int:
    correct = 0
    for prompt, expected in CASES:
        resp = await complete([Message.user_text(prompt)], model="claude-haiku-4-5-20251001",
                              tools=[schema], max_tokens=512)
        got = ""
        if resp.tool_uses:
            got = str(resp.tool_uses[0].input.get("severity", "")).lower()
        ok = got == expected
        correct += ok
        mark = "✓" if ok else "✗"
        print(f"  [{name:8}] expected={expected:6} got={got or '(none)':9} {mark}  {prompt[:38]}")
    print(f"  => {name}: {correct}/{len(CASES)}\n")
    return correct


async def main() -> None:
    for name, schema in VARIANTS.items():
        await run_variant(name, schema)


asyncio.run(main())