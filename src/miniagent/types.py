from __future__ import annotations
from typing import Annotated, Literal, Any
from pydantic import BaseModel, Field

Role = Literal["user", "assistant"]

class TextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class ToolResultBlock(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: str
    is_error: bool = False

ContentBlock = Annotated[
    TextBlock | ToolUseBlock | ToolResultBlock,
    Field(discriminator="type"),
]

class Message(BaseModel):
    role: Role
    content: list[ContentBlock]

    @classmethod
    def user_text(cls, text: str) -> Message:
        return cls(role="user", content=[TextBlock(text=text)])

    @classmethod
    def assistant_text(cls, text: str) -> Message:
        return cls(role="assistant", content=[TextBlock(text=text)])

class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

StopReason = Literal["end_turn", "tool_use", "max_tokens", "stop_sequence", "other"]

class Response(BaseModel):
    content: list[ContentBlock]
    stop_reason: StopReason
    usage: Usage
    model: str
    raw: dict[str, Any] = Field(default_factory=dict, repr=False)

    @property
    def tool_uses(self) -> list[ToolUseBlock]:
        return [b for b in self.content if isinstance(b, ToolUseBlock)]

    def to_message(self) -> Message:
        return Message(role="assistant", content=self.content)