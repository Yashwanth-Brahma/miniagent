# src/miniagent/tools/dangerous.py
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Annotated

from pydantic import Field

from miniagent.tools.registry import tool

# The allowlist: ONLY these commands can run. Everything else is refused
# in CODE — no amount of model persuasion changes this set.
ALLOWED_COMMANDS = {"ls", "cat", "head", "tail", "wc", "grep", "find", "pwd", "echo"}

WORKSPACE = Path("./workspace").resolve()   # the jail — tools can't escape this

@tool
def shell(
    command: Annotated[str, Field(description="A shell command to run. Only a small allowlist of read-only commands is permitted.")],
) -> str:
    """Run a read-only shell command inside the workspace. Only safe, allowlisted commands are permitted."""
    parts = command.split()
    if not parts:
        return "Error: empty command."

    program = parts[0]
    if program not in ALLOWED_COMMANDS:
        return (f"Error: '{program}' is not allowed. "
                f"Permitted commands: {sorted(ALLOWED_COMMANDS)}")

    try:
        result = subprocess.run(
            parts,                      # a LIST, never a string — see note below
            cwd=WORKSPACE,              # run inside the jail
            capture_output=True,
            text=True,
            timeout=10,                 # never hang the agent
            shell=False,                # CRITICAL — see note below
        )
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 10s."

    output = result.stdout[:5000]
    if result.stderr:
        output += f"\n[stderr] {result.stderr[:1000]}"
    return output or "(no output)"

import sqlite3

DB_PATH = Path("./workspace/data.db").resolve()

@tool(requires_approval=True)
def write_file(
    path: Annotated[str, Field(description="File path relative to the workspace. Cannot escape the workspace.")],
    content: Annotated[str, Field(description="Text content to write")],
) -> str:
    """Write text to a file inside the workspace. Paths that escape the workspace are refused."""
    # resolve the FULL absolute path, collapsing any ../ segments
    target = (WORKSPACE / path).resolve()

    # THE JAIL CHECK: is the resolved path actually inside the workspace?
    if not target.is_relative_to(WORKSPACE):
        return f"Error: '{path}' escapes the workspace. Refused."

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Wrote {len(content)} chars to {target.relative_to(WORKSPACE)}"

@tool
def sql_query(
    query: Annotated[str, Field(description="A read-only SQL SELECT query.")],
) -> str:
    """Run a read-only SQL query against the workspace database. Only SELECT-style reads are possible."""
    # THE STAR DEFENSE: open the DB in read-only mode at the CONNECTION level.
    # A read-only connection physically cannot execute writes — the query text is irrelevant.
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        return f"Error: could not open database read-only: {e}"

    try:
        cursor = conn.execute(query)
        rows = cursor.fetchmany(100)              # cap results — cost + memory
        cols = [d[0] for d in cursor.description] if cursor.description else []
        conn.close()
    except sqlite3.OperationalError as e:
        conn.close()
        return f"Error running query: {e}"        # a write attempt lands HERE

    header = " | ".join(cols)
    body = "\n".join(" | ".join(str(v) for v in row) for row in rows)
    return f"{header}\n{body}" if body else "(no rows)"