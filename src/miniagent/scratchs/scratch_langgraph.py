from __future__ import annotations
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode
# define tools as LangChain tools (or adapt yours) — e.g. a simple one:
from langchain_core.tools import tool as lc_tool
load_dotenv()  # load .env for API keys

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # the conversation, auto-appended. This is the "state" of the agent.


@lc_tool
def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"It's sunny in {city}."

tools = [get_weather]
llm = ChatAnthropic(model="claude-haiku-4-5-20251001").bind_tools(tools)
tool_node = ToolNode(tools)

def call_model(state: AgentState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}          # add_messages appends it

def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    # if the model asked for tools, go run them; otherwise we're done
    return "tools" if last.tool_calls else END

graph = StateGraph(AgentState)
graph.add_node("model", call_model)
graph.add_node("tools", tool_node)
graph.set_entry_point("model")
graph.add_conditional_edges("model", should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "model")          # after tools, loop back to model
# app = graph.compile()

# result = app.invoke({"messages": [HumanMessage(content="What's the weather in Bengaluru?")]})
# print(result["messages"][-1].content)

from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
# app = graph.compile(checkpointer=checkpointer)   # <-- the whole feature

# # now every invocation needs a thread_id to identify the conversation
# config = {"configurable": {"thread_id": "conversation-1"}}

# result = app.invoke({"messages": [HumanMessage(content="What's the weather in Bengaluru?")]}, config)
# print(result["messages"][-1].content)

# # ask a FOLLOW-UP — it remembers the conversation, no manual history passing
# result2 = app.invoke({"messages": [HumanMessage(content="What about Mumbai?")]}, config)
# print(result2["messages"][-1].content)

# compile with an interrupt before the tools node
app = graph.compile(checkpointer=checkpointer, interrupt_before=["tools"])

config = {"configurable": {"thread_id": "approval-demo"}}

# run — it STOPS before executing tools
result = app.invoke({"messages": [HumanMessage(content="What's the weather in Delhi?")]}, config)

# the graph paused. inspect what it WANTS to do:
state = app.get_state(config)
print("about to run:", state.values["messages"][-1].tool_calls)

# a human decides. to approve, just resume with no new input:
result = app.invoke(None, config)   # None = "continue from where you paused"
print(result["messages"][-1].content)