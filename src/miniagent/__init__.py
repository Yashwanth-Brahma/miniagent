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

# import functools

# def loud(fn):
#     @functools.wraps(fn)          # <-- copies name, docstring, etc. from fn
#     def wrapper(*args, **kwargs):
#         print(f"calling {fn.__name__}")
#         return fn(*args, **kwargs)
#     return wrapper

# @loud
# def add(a, b):
#     """Add two numbers."""
#     return a + b

# print(add.__name__)   # "add"              ✓
# print(add.__doc__)    # "Add two numbers." ✓

# import inspect
# from typing import Annotated
# from pydantic import Field

# def read_file( path: Annotated[str, Field(description="Path to a UTF-8 text file, relative to the workspace root")],
#     max_bytes: Annotated[int, Field(description="Maximum bytes to read")] = 50_000,) -> str:
#     """Read a UTF-8 text file. Returns the file contents."""
#     ...

# sig = inspect.signature(read_file)
# for name, param in sig.parameters.items():
#     print(name, "|", param.annotation, "|", param.kind, "|", param.default)

# from pydantic import create_model, Field
# import inspect

# def tool_schema(fn) -> dict:
#     sig = inspect.signature(fn)
#     fields = {}
#     for name, param in sig.parameters.items():
#         annotation = param.annotation
#         default = ... if param.default is inspect.Parameter.empty else param.default
#         fields[name] = (annotation, default)
#     Model = create_model(fn.__name__, **fields)
#     return {
#         "name": fn.__name__,
#         "description": (fn.__doc__ or "").strip(),
#         "input_schema": Model.model_json_schema(),
#     }

# import json
# print(json.dumps(tool_schema(read_file), indent=2))

# from miniagent.types import ToolUseBlock
# from miniagent.tools.dispatch import dispatch
# import miniagent.tools.registry  # ensures read_file is registered (import side effect)

# # happy path
# block = ToolUseBlock(id="t1", name="read_file", input={"path": "src/miniagent/test.md"})
# print("id:", block.id, "| content:", dispatch(block).content[:60])

# # tool doesn't exist
# bad_name = ToolUseBlock(id="t2", name="delete_everything", input={})
# print("id:", bad_name.id, "| content:", dispatch(bad_name).content, "| is_error:", dispatch(bad_name).is_error)

# # tool exists but args are wrong (missing required 'path')
# bad_args = ToolUseBlock(id="t3", name="read_file", input={})
# print("id:", bad_args.id, "| content:", dispatch(bad_args).content, "| is_error:", dispatch(bad_args).is_error)

# from miniagent.tools.dispatch import dispatch
# from miniagent.types import ToolUseBlock
# # print(dispatch(ToolUseBlock(id="d1", name="list_dir", input={"path": "."})).content)

# print(dispatch(ToolUseBlock(id="h1", name="http_get",
#     input={"url": "https://api.github.com"})).content[:200])

# # and a failure path
# print(dispatch(ToolUseBlock(id="h2", name="http_get",
#     input={"url": "not-a-url"})).content)