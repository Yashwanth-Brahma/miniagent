import asyncio
from miniagent.memory.store import MemoryStore
from miniagent.memory.summarize import run_with_memory, summarize_messages
from miniagent.types import Message

async def main():
    # simulate a long conversation with a task up front and facts scattered through
    # convo = [
    #     Message.user_text("Help me refactor the auth module to use JWT instead of sessions."),
    #     Message.assistant_text("I'll help. First, where is auth currently handled?"),
    #     Message.user_text("In auth.py, using Flask sessions. The secret key is in config.py."),
    #     Message.assistant_text("Got it. Sessions are set in login() at auth.py line 40."),
    #     # ... imagine 20 more turns of back-and-forth ...
    #     Message.user_text("Also remember we need to keep the /legacy endpoint working."),
    #     Message.assistant_text("Noted. Legacy endpoint stays on sessions."),
    # ]

    # summary = await summarize_messages(convo, model="claude-haiku-4-5-20251001")
    # print("SUMMARY:\n", summary)
    mem = MemoryStore()
    mem.add("The user's secret key is stored in config.py")
    mem.add("The /legacy endpoint must keep using sessions, not JWT")
    mem.add("The user prefers TypeScript over JavaScript")
    mem.add("Session setup happens in auth.py at line 40")

    print(await run_with_memory("where do I find the secret key?", mem, model="claude-haiku-4-5-20251001"))
    print(await run_with_memory("what should I not migrate to JWT?", mem, model="claude-haiku-4-5-20251001"))

asyncio.run(main())