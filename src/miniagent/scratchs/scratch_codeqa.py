# scratch_codeqa.py
import asyncio
from miniagent.agent import run
from miniagent.retrieval.index import CodeIndex
from miniagent.tools.code_search import set_index
import miniagent.tools.code_search   # registers search_code

async def main():
    set_index(CodeIndex.build("/tmp/flask/src/flask"))
    result = await run(
        "How does Flask match an incoming URL to a view function? Cite the source.",
        max_steps=15,
        max_repeats=5,
        model="gpt-4o-mini",
        
    )
    print(result.output)

asyncio.run(main())