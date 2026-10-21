"""Named Experiments: each name builds one Searcher stack, and its settings say how."""

from collections.abc import Callable

import psycopg

from sec_filings_analyst.embedder import Embedder
from sec_filings_analyst.evaluation import Experiment, Searcher
from sec_filings_analyst.retriever import Retriever

# name → (settings recorded in each run, builder of the Searcher)
EXPERIMENTS: dict[str, tuple[dict, Callable[[psycopg.Connection, Embedder], Searcher]]] = {
    "dense-baseline": ({"retriever": "dense, exact cosine"}, Retriever),
}


def build_experiment(name: str, conn: psycopg.Connection, embedder: Embedder) -> Experiment:
    """Raises ValueError for an unknown name, listing the known ones."""
    if name not in EXPERIMENTS:
        raise ValueError(f"unknown experiment {name!r}; known: {', '.join(EXPERIMENTS)}")
    settings, build = EXPERIMENTS[name]
    return Experiment(name, settings, build(conn, embedder))
