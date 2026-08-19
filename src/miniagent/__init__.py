# import asyncio
# from anthropic import AsyncAnthropic
# from dotenv import load_dotenv
# load_dotenv()

# async def main() -> None:
#     client = AsyncAnthropic()
#     models = await client.models.list(limit=50)
#     for m in models.data:
#         print(m.id, "|", m.display_name)

# asyncio.run(main())
# from miniagent.context import fit_to_budget
# from miniagent.types import Message

# convo = [Message.user_text("TASK: refactor the auth module")]
# for i in range(30):
#     convo.append(Message.assistant_text(f"step {i}: did some work " * 20))

# tight = 500  # force it to drop things

# trunc = fit_to_budget(convo, max_tokens=tight, model="gpt-4o-mini", strategy="truncate_oldest")
# slide = fit_to_budget(convo, max_tokens=tight, model="gpt-4o-mini", strategy="sliding_window")

# print("truncate kept the task?  ", "TASK" in trunc[0].content[0].text)
# print("sliding kept the task?   ", "TASK" in slide[0].content[0].text)