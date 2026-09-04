from miniagent.retrieval.golden import CODE_GOLDEN
from typing import Callable


def score(search_fn: Callable[[str, int], list], k: int = 3) -> None:
    """search_fn(query, k) -> list of chunk objects with a .text attribute."""
    hits_at_1 = hits_at_k = 0
    ranks = []
    for case in CODE_GOLDEN:
        results = search_fn(case.query, k)
        rank = next((i + 1 for i, r in enumerate(results)
                     if case.must_contain.lower() in r.text.lower()), None)
        if rank == 1: hits_at_1 += 1
        if rank is not None:
            hits_at_k += 1
            ranks.append(rank)
        print(f"  rank {rank if rank else '—'}  {case.query[:45]}")
    avg = sum(ranks) / len(ranks) if ranks else 0
    print(f"\n  recall@1: {hits_at_1}/{len(CODE_GOLDEN)}  |  recall@{k}: {hits_at_k}/{len(CODE_GOLDEN)}  |  avg rank: {avg:.1f}")