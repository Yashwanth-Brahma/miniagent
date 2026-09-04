from __future__ import annotations
from pydantic import BaseModel


class GoldenCase(BaseModel):
    query: str
    # a substring that MUST appear in a correctly-retrieved chunk
    must_contain: str


# ~12-15 cases covering the doc + your known failure modes
GOLDEN: list[GoldenCase] = [
    GoldenCase(query="what happens to accumulators after a crash?",
               must_contain="restored from storage"),
    GoldenCase(query="how do I log in?",                       # vocab: doc says "authenticate"
               must_contain="credential"),
    GoldenCase(query="how to set up?",                          # vagueness (Day 2 killer)
               must_contain="binary"),
    GoldenCase(query="what database backends are supported?",
               must_contain="replicated"),
    GoldenCase(query="how does backpressure work?",
               must_contain="bounded buffer"),
    GoldenCase(query="what happens when a record can't be processed?",
               must_contain="dead letter"),
    GoldenCase(query="how are credentials rotated?",
               must_contain="grace period"),
    GoldenCase(query="how do nodes find each other?",
               must_contain="coordination service"),
    GoldenCase(query="what does compaction do?",
               must_contain="reclaims"),
    GoldenCase(query="how do I upgrade without downtime?",
               must_contain="drain"),
]

CODE_GOLDEN = [
    # exact-identifier queries — BM25 should shine, vector may blur
    GoldenCase(query="send_file", must_contain="send_file"),
    GoldenCase(query="url_for function", must_contain="def url_for"),
    GoldenCase(query="Blueprint register", must_contain="register"),
    # semantic queries — vector should shine, BM25 may miss
    GoldenCase(query="how does routing match a URL to a view?", must_contain="route"),
    GoldenCase(query="how are request contexts managed?", must_contain="context"),
    GoldenCase(query="how does it handle errors and exceptions?", must_contain="handle"),
    # ambiguous — the reranker's chance to disambiguate
    GoldenCase(query="how is configuration loaded?", must_contain="config"),
    GoldenCase(query="how does session data get signed?", must_contain="session"),
]