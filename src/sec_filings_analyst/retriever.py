"""Searchers: the top-k Chunks for a query. Evaluation and the agent both search through them."""

from dataclasses import dataclass
from typing import Protocol

import psycopg

from sec_filings_analyst.bm25 import Bm25
from sec_filings_analyst.documents import Chunk, Document
from sec_filings_analyst.embedder import Embedder, to_pgvector


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float  # higher is closer; the scale depends on the Searcher (cosine, BM25, RRF)


class Searcher(Protocol):
    def search(self, query: str, k: int) -> list[SearchResult]: ...


_COLUMNS = "d.name, d.company, d.doc_type, d.fiscal_year, c.page, c.position, c.text, c.token_count"


class Retriever:
    """Dense-only, exact (no approximate index) cosine search over every stored Chunk.

    Needs an autocommit connection, so searches never hold a transaction open."""

    def __init__(self, conn: psycopg.Connection, embedder: Embedder):
        self._conn = conn
        self._embedder = embedder

    def search(self, query: str, k: int) -> list[SearchResult]:
        """The k Chunks nearest the query, nearest first."""
        (embedding,) = self._embedder.embed([query])
        rows = self._conn.execute(
            f"SELECT {_COLUMNS}, 1 - (c.embedding <=> %(q)s::vector) AS score"
            " FROM chunks c JOIN documents d ON d.id = c.document_id"
            " ORDER BY c.embedding <=> %(q)s::vector, c.id LIMIT %(k)s",
            {"q": to_pgvector(embedding), "k": k},
        ).fetchall()
        return _results(rows)


class KeywordSearcher:
    """BM25 over each Chunk's Postgres 'english' lexemes: a Chunk sharing any term with the
    query can match (AND-ing every word of a long Question would match almost nothing). Loads
    every Chunk's lexeme counts once, when built. Needs an autocommit connection, like Retriever."""

    def __init__(self, conn: psycopg.Connection):
        self._conn = conn
        rows = conn.execute(
            "SELECT u.lexeme, array_agg(c.id), array_agg(cardinality(u.positions))"
            " FROM chunks c, unnest(c.tsv) u GROUP BY u.lexeme"
        ).fetchall()
        self._index = Bm25({lexeme: dict(zip(ids, tfs, strict=True)) for lexeme, ids, tfs in rows})

    def search(self, query: str, k: int) -> list[SearchResult]:
        """The k Chunks that best match the query's terms, best first; none share a term → []."""
        (terms,) = self._conn.execute(
            "SELECT array(SELECT lexeme FROM unnest(to_tsvector('english', %s)))", [query]
        ).fetchone()
        top = self._index.top(terms, k)
        rows = self._conn.execute(
            f"SELECT c.id, {_COLUMNS} FROM chunks c JOIN documents d ON d.id = c.document_id"
            " WHERE c.id = ANY(%s)",
            [[chunk for chunk, _ in top]],
        ).fetchall()
        columns = {row[0]: row[1:] for row in rows}
        return _results([(*columns[chunk], score) for chunk, score in top])


RRF_K = 60  # the usual constant: the higher it is, the less a top rank outweighs a lower one


class HybridSearcher:
    """Fuses other Searchers' rankings with Reciprocal Rank Fusion: each is asked for
    max(k, candidates) Chunks, and a Chunk scores the sum of 1/(RRF_K + rank) over the lists it
    appears in. Ties keep the order Chunks were first seen in, earlier Searchers first."""

    def __init__(self, searchers: list[Searcher], candidates: int):
        self._searchers = searchers
        self._candidates = candidates

    def search(self, query: str, k: int) -> list[SearchResult]:
        """The k Chunks with the highest fused score, highest first."""
        depth = max(k, self._candidates)
        scores: dict[Chunk, float] = {}
        for searcher in self._searchers:
            for rank, result in enumerate(searcher.search(query, depth), start=1):
                scores[result.chunk] = scores.get(result.chunk, 0.0) + 1 / (RRF_K + rank)
        top = sorted(scores.items(), key=lambda item: -item[1])[:k]
        return [SearchResult(chunk, score) for chunk, score in top]


def _results(rows: list[tuple]) -> list[SearchResult]:
    results = []
    for name, company, doc_type, fiscal_year, page, position, text, token_count, score in rows:
        document = Document(name, company, doc_type, fiscal_year)
        chunk = Chunk(document, page, position, text, token_count)
        results.append(SearchResult(chunk, score))
    return results
