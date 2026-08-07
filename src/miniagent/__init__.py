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
