from __future__ import annotations

from typing import Any

from miniagent.tools.registry import REGISTRY
from miniagent.types import ToolResultBlock, ToolUseBlock
import miniagent.tools.dangerous  # registers shell and write_file


def dispatch(block: ToolUseBlock) -> ToolResultBlock:
    # 1. FIND the tool by name
    fn = REGISTRY.get(block.name)
    if fn is None:
        return ToolResultBlock(
            tool_use_id=block.id,
            content=f"Error: no tool named '{block.name}'. Available: {list(REGISTRY)}",
            is_error=True,
        )

    # 2. RUN it with the model's args, catching anything that goes wrong
    try:
        result = fn(**block.input)
    except Exception as e:
        return ToolResultBlock(
            tool_use_id=block.id,
            content=f"Error running '{block.name}': {e!r}",
            is_error=True,
        )

    # 3. PACKAGE the result
    return ToolResultBlock(
        tool_use_id=block.id,
        content=str(result),
        is_error=False,
    )