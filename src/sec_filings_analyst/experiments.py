"""Named Experiments: each name builds one Searcher stack, and its settings say how."""

from collections.abc import Callable
from dataclasses import dataclass

import psycopg

from sec_filings_analyst.bm25 import K1, B
from sec_filings_analyst.embedder import Embedder
from sec_filings_analyst.retriever import (
    RRF_K,
    HybridSearcher,
    KeywordSearcher,
    Retriever,
    Searcher,
)


@dataclass(frozen=True)
class Experiment:
    name: str
    settings: dict  # how its Searcher is built; recorded in each run
    searcher: Searcher


DENSE = "dense, exact cosine"
KEYWORD = f"keyword, BM25 (k1 {K1}, b {B}) over Postgres 'english' lexemes, any term"
# Per Searcher; more than the eval's 50 Chunks, so a Chunk just past one list's cut can still count
HYBRID_CANDIDATES = 100

# name → (settings recorded in each run, builder of the Searcher)
EXPERIMENTS: dict[str, tuple[dict, Callable[[psycopg.Connection, Embedder], Searcher]]] = {
    "dense-baseline": ({"retriever": DENSE}, Retriever),
    "keyword-bm25": ({"retriever": KEYWORD}, lambda conn, embedder: KeywordSearcher(conn)),
    "hybrid-rrf": (
        {
            "retriever": f"hybrid, RRF (k {RRF_K}) of [{DENSE}] + [{KEYWORD}]",
            "candidates": HYBRID_CANDIDATES,
        },
        lambda conn, embedder: HybridSearcher(
            [Retriever(conn, embedder), KeywordSearcher(conn)], HYBRID_CANDIDATES
        ),
    ),
}


def build_experiment(name: str, conn: psycopg.Connection, embedder: Embedder) -> Experiment:
    """Raises ValueError for an unknown name, listing the known ones."""
    if name not in EXPERIMENTS:
        raise ValueError(f"unknown experiment {name!r}; known: {', '.join(EXPERIMENTS)}")
    settings, build = EXPERIMENTS[name]
    return Experiment(name, settings, build(conn, embedder))
