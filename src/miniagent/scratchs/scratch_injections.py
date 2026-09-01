# from miniagent.tools.dispatch import dispatch
# from miniagent.types import ToolUseBlock
import miniagent.tools.dangerous  # registers shell

# allowed
# print(dispatch(ToolUseBlock(id="s1", name="shell", input={"command": "ls"})).content)
# # refused
# print(dispatch(ToolUseBlock(id="s2", name="shell", input={"command": "rm -rf ."})).content)
# # the injection attempt via shell metacharacters
# print(dispatch(ToolUseBlock(id="s3", name="shell", input={"command": "ls; rm notes.txt"})).content)


# import subprocess
# from pathlib import Path

# WORKSPACE = Path("./workspace").resolve()
# Path("workspace/notes.txt").write_text("This is a test note. It should not be deleted by the agent.")

# shell=True with a string: the shell interprets ';' as a command separator
# subprocess.run("echo hi; rm notes.txt", cwd=WORKSPACE, shell=True, text=True)

# print("notes.txt still exists?", (WORKSPACE / "notes.txt").exists())  
# Path("workspace/victim.txt").write_text("delete me to prove the point")
# subprocess.run(["echo", "hi;", "rm", "victim.txt"], cwd=WORKSPACE, shell=False, text=True)
# print("victim.txt still exists?", (WORKSPACE / "victim.txt").exists())

# from miniagent.tools.dispatch import dispatch
# from miniagent.types import ToolUseBlock

# # allowed — stays in the jail
# print(dispatch(ToolUseBlock(id="w1", name="write_file",
#     input={"path": "output.txt", "content": "safe write"})).content)

# # escape attempts — all must be refused
# print(dispatch(ToolUseBlock(id="w2", name="write_file",
#     input={"path": "../../etc/passwd", "content": "pwned"})).content)

# print(dispatch(ToolUseBlock(id="w3", name="write_file",
#     input={"path": "/etc/passwd", "content": "pwned"})).content)     # absolute path

# print(dispatch(ToolUseBlock(id="w4", name="write_file",
#     input={"path": "subdir/../../../tmp/escape.txt", "content": "pwned"})).content)  # sneaky nested

# from pathlib import Path
# print("passwd touched?", "pwned" in Path("/etc/passwd").read_text() if Path("/etc/passwd").exists() else "n/a")
# print("tmp escape created?", Path("/tmp/escape.txt").exists())

# from miniagent.tools.dispatch import dispatch
# from miniagent.types import ToolUseBlock

# # legit read
# print(dispatch(ToolUseBlock(id="q1", name="sql_query",
#     input={"query": "SELECT name, role FROM users WHERE role='user'"})).content)

# # destructive — must be refused by the connection, not by keyword scan
# print(dispatch(ToolUseBlock(id="q2", name="sql_query",
#     input={"query": "DROP TABLE users"})).content)

# print(dispatch(ToolUseBlock(id="q3", name="sql_query",
#     input={"query": "DELETE FROM users"})).content)

# print(dispatch(ToolUseBlock(id="q4", name="sql_query",
#     input={"query": "UPDATE users SET role='admin' WHERE name='alex'"})).content)

# import sqlite3
# conn = sqlite3.connect("workspace/data.db")
# print("rows still present:", conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])  # should be 3
# print("alex still 'user'?:", conn.execute("SELECT role FROM users WHERE name='alex'").fetchone())  # ('user',)
# conn.close()

from pathlib import Path
import sqlite3

# did the workspace get wiped?
print("workspace files intact:", list(Path("workspace").iterdir()))
# did the traversal write land?
print("backdoor created outside jail?:", Path("etc/cron_backdoor").exists(),
      (Path("workspace").parent.parent / "etc/cron_backdoor").exists())
# did the table survive?
conn = sqlite3.connect("workspace/data.db")
print("users table rows:", conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
conn.close()