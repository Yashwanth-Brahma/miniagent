from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from pydantic import create_model
from pathlib import Path

# the lookup table: tool name -> the callable
REGISTRY: dict[str, Callable[..., Any]] = {}


def tool_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    sig = inspect.signature(fn)
    fields = {}
    for name, param in sig.parameters.items():
        annotation = param.annotation
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[name] = (annotation, default)
    model = create_model(fn.__name__, **fields)
    return {
        "name": fn.__name__,
        "description": (fn.__doc__ or "").strip(),
        "input_schema": model.model_json_schema(),
    }


def tool(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Register a function as an agent tool."""
    schema = tool_schema(fn) # <-- your Idea 3: compute schema once, attach to wrapper and preserve __name__/__doc__

    @functools.wraps(fn)              # <-- your Idea 4: keeps __name__ / __doc__
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    wrapper.tool_schema = schema      # attach schema to the function object
    REGISTRY[fn.__name__] = wrapper   # register by name as the callable. Any code that imports this module can now call REGISTRY["read_file"](...) to invoke the tool.
    return wrapper

def all_tool_schemas() -> list[dict[str, Any]]:
    return [fn.tool_schema for fn in REGISTRY.values()]

from typing import Annotated
from pydantic import Field



@tool
def read_file(
    path: Annotated[str, Field(description="Path to a UTF-8 text file, relative to workspace root")],
    max_bytes: Annotated[int, Field(description="Maximum bytes to read")] = 50_000,
) -> str:
    """Read a UTF-8 text file and return its contents."""
    from pathlib import Path
    return Path(path).read_text()[:max_bytes]

@tool
def list_dir(
    path: Annotated[str, Field(description="Directory path relative to workspace root")] = ".",
) -> str:
    """List the files and subdirectories in a directory, one per line."""
    p = Path(path)
    if not p.exists():
        return f"Error: path '{path}' does not exist."
    if not p.is_dir():
        return f"Error: '{path}' is a file, not a directory."
    entries = sorted(p.iterdir())
    lines = [f"{'DIR ' if e.is_dir() else 'FILE'} {e.name}" for e in entries]
    return "\n".join(lines) if lines else "(empty directory)"

import httpx

@tool
def http_get(
    url: Annotated[str, Field(description="Full URL to fetch, must start with http:// or https://")],
    max_chars: Annotated[int, Field(description="Max characters of the response body to return")] = 5_000,
) -> str:
    """Fetch the text body of a URL via HTTP GET. Returns truncated response text."""
    if not url.startswith(("http://", "https://")):
        return f"Error: url must start with http:// or https://, got '{url}'"
    try:
        resp = httpx.get(url, timeout=10.0, follow_redirects=True)
    except httpx.TimeoutException:
        return f"Error: request to '{url}' timed out after 10s."
    except httpx.RequestError as e:
        return f"Error fetching '{url}': {e!r}"
    body = resp.text[:max_chars]
    suffix = "" if len(resp.text) <= max_chars else f"\n...[truncated, {len(resp.text)} total chars]"
    return f"HTTP {resp.status_code}\n{body}{suffix}"

# print(REGISTRY.keys())                    # dict_keys(['read_file'])
# print(read_file.tool_schema["name"])      # read_file
# print(read_file("src/miniagent/test.md")[:50])     # still callable normally!

# print(all_tool_schemas())