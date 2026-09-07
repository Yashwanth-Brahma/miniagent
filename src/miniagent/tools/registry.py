from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from pydantic import create_model
from pathlib import Path

# the lookup table: tool name -> the callable
REGISTRY: dict[str, Callable[..., Any]] = {}
BLOCKED = {".env", ".git", "credentials", "id_rsa", ".pem", ".key"}

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


def tool(fn = None, *, requires_approval: bool = False):
    """Register a function as an agent tool. Set requires_approval=True for irreversible actions."""
    def decorator(f):
        schema = tool_schema(f)

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            return f(*args, **kwargs)

        wrapper.tool_schema = schema
        wrapper.requires_approval = requires_approval   # <-- the flag rides on the function
        REGISTRY[f.__name__] = wrapper
        return wrapper

    # supports both @tool and @tool(requires_approval=True)
    return decorator(fn) if fn else decorator

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
    p = Path(path)
    if any(part in BLOCKED or part.startswith(".env") for part in p.parts) \
       or p.suffix in {".pem", ".key"}:
        return "Error: reading secret/credential files is not permitted."
    print(f"[read_file] path={path}, max_bytes={max_bytes}")
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
    print(f"[http_get] url={url}, max_chars={max_chars}")
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

@tool
def check_status(service: str) -> str:
    """Check whether a service is running."""
    return "Error: service registry unavailable, retry."