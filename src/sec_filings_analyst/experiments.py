"""Named Experiments: each name builds one Searcher stack, and its settings say how."""

from collections.abc import Callable
from dataclasses import dataclass

import psycopg

from sec_filings_analyst import cross_encoder
from sec_filings_analyst.bm25 import K1, B
from sec_filings_analyst.embedder import Embedder
from sec_filings_analyst.retriever import (
    RRF_K,
    HybridSearcher,
    KeywordSearcher,
    RerankingSearcher,
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
# Per Searcher, or k if larger: at the eval's k (50) each list reaches past k, so a Chunk just past
# one list's cut can still count
HYBRID_CANDIDATES = 100
RERANKER = f"cross-encoder {cross_encoder.MODEL}@{cross_encoder.REVISION[:7]}, ONNX on CPU"


Builder = Callable[[psycopg.Connection, Embedder], Searcher]


def _dense_reranked(candidates: int) -> tuple[dict, Builder]:
    settings = {"retriever": f"rerank [{DENSE}] by {RERANKER}", "candidates": candidates}
    return settings, lambda conn, embedder: RerankingSearcher(
        Retriever(conn, embedder), cross_encoder.CrossEncoderScorer(), candidates
    )


# name → (settings recorded in each run, builder of the Searcher)
EXPERIMENTS: dict[str, tuple[dict, Builder]] = {
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
    # Candidates tuned on dev only: reranking 50 re-orders dense's Chunks, 100 also widens the pool
    "dense-rerank-50": _dense_reranked(50),
    "dense-rerank-100": _dense_reranked(100),
}


def build_experiment(name: str, conn: psycopg.Connection, embedder: Embedder) -> Experiment:
    """Raises ValueError for an unknown name, listing the known ones."""
    if name not in EXPERIMENTS:
        raise ValueError(f"unknown experiment {name!r}; known: {', '.join(EXPERIMENTS)}")
    settings, build = EXPERIMENTS[name]
    return Experiment(name, settings, build(conn, embedder))
