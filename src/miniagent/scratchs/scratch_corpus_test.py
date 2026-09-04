from pathlib import Path
from miniagent.retrieval.code_chunker import chunk_python

REPO = Path("/tmp/flask/src")
files = list(REPO.rglob("*.py"))
print(f"{len(files)} python files")

chunks = []
for f in files:
    try:
        text = f.read_text(encoding="utf-8")
    except Exception:
        continue
    # keep the file path relative, for citations + so you know where chunks came from
    rel = str(f.relative_to(REPO.parent))
    chunks.extend(chunk_python(text, source=rel))

print(f"{len(chunks)} chunks across the corpus")

# for needle in ["def send_file"]:
#     matches = [c for c in chunks if needle in c.text]
#     print(f"{needle!r}: in {len(matches)} chunks")
#     if matches:
#         print("   sample:", repr(matches[0].text))

for c in chunks:
    if "def send_file" in c.text:
        print(repr(c))
        print("---")