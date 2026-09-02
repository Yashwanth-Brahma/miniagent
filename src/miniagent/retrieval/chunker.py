from __future__ import annotations

import re
from pydantic import BaseModel


class Chunk(BaseModel):
    text: str
    source: str           # which file this came from
    start_line: int       # for citations later
    end_line: int


def split_sentences(text: str) -> list[tuple[str, int]]:
    """Split into (sentence, line_number) pairs. Crude but boundary-aware."""
    sentences = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        # split each line on sentence enders, keep non-empty pieces
        for piece in re.split(r"(?<=[.!?])\s+", line):
            piece = piece.strip()
            if piece:
                sentences.append((piece, line_no))
    return sentences


def chunk_text(
    text: str,
    source: str,
    *,
    target_chars: int = 500,
    overlap_sentences: int = 1,
) -> list[Chunk]:
    sentences = split_sentences(text)
    chunks: list[Chunk] = []
    i = 0
    while i < len(sentences):
        chunk_start = i               # remember where THIS chunk began
        current: list[tuple[str, int]] = []
        size = 0
        while i < len(sentences) and size < target_chars:
            sent, line = sentences[i]
            current.append((sent, line))
            size += len(sent)
            i += 1
        if not current:
            break
        chunks.append(Chunk(
            text=" ".join(s for s, _ in current),
            source=source,
            start_line=current[0][1],
            end_line=current[-1][1],
        ))
        # overlap, BUT guarantee we advance past where this chunk started
        next_start = i - overlap_sentences
        if next_start <= chunk_start:      # overlap would stall or go backward
            next_start = chunk_start + 1   # force at least one sentence of progress
        i = next_start
    return chunks