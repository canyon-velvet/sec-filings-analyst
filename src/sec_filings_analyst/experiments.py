"""Named Experiments: each name builds one Searcher stack, and its settings say how."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import psycopg

from sec_filings_analyst.bm25 import K1, B
from sec_filings_analyst.embedder import Embedder
from sec_filings_analyst.retriever import KeywordSearcher, Retriever, SearchResult


class Searcher(Protocol):
    def search(self, query: str, k: int) -> list[SearchResult]: ...


@dataclass(frozen=True)
class Experiment:
    name: str
    settings: dict  # how its Searcher is built; recorded in each run
    searcher: Searcher


# name → (settings recorded in each run, builder of the Searcher)
EXPERIMENTS: dict[str, tuple[dict, Callable[[psycopg.Connection, Embedder], Searcher]]] = {
    "dense-baseline": ({"retriever": "dense, exact cosine"}, Retriever),
    "keyword-bm25": (
        {"retriever": f"keyword, BM25 (k1 {K1}, b {B}) over Postgres 'english' lexemes, any term"},
        lambda conn, embedder: KeywordSearcher(conn),
    ),
}


def build_experiment(name: str, conn: psycopg.Connection, embedder: Embedder) -> Experiment:
    """Raises ValueError for an unknown name, listing the known ones."""
    if name not in EXPERIMENTS:
        raise ValueError(f"unknown experiment {name!r}; known: {', '.join(EXPERIMENTS)}")
    settings, build = EXPERIMENTS[name]
    return Experiment(name, settings, build(conn, embedder))
