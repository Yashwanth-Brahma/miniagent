import asyncio
from miniagent.retry import llm_retry
from miniagent.errors import LLMError

attempts = 0

@llm_retry
async def flaky():
    global attempts
    attempts += 1
    print(f"  attempt {attempts}")
    if attempts < 3:
        raise LLMError("simulated overload", retryable=False, status=529)
    return "success!"

async def main():
    result = await flaky()
    print("result:", result, "| took", attempts, "attempts")

asyncio.run(main())