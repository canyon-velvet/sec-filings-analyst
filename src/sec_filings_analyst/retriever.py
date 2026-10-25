"""Searchers: the top-k Chunks for a query. Evaluation and the agent both search through them."""

from dataclasses import asdict, dataclass
from typing import Protocol

import psycopg

from sec_filings_analyst.bm25 import Bm25
from sec_filings_analyst.documents import Chunk, Document
from sec_filings_analyst.embedder import Embedder, to_pgvector


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float  # higher is closer; the scale depends on the Searcher (cosine, BM25, RRF, Scorer)


@dataclass(frozen=True)
class Filter:
    """Which Documents a search may return Chunks from: each field set must match; None matches
    any value."""

    company: str | None = None
    doc_type: str | None = None
    fiscal_year: int | None = None


class Searcher(Protocol):
    def search(self, query: str, k: int, filter: Filter | None = None) -> list[SearchResult]: ...


_COLUMNS = "d.name, d.company, d.doc_type, d.fiscal_year, c.page, c.position, c.text, c.token_count"


class Retriever:
    """Dense-only, exact (no approximate index) cosine search over every stored Chunk.

    Needs an autocommit connection, so searches never hold a transaction open."""

    def __init__(self, conn: psycopg.Connection, embedder: Embedder):
        self._conn = conn
        self._embedder = embedder

    def search(self, query: str, k: int, filter: Filter | None = None) -> list[SearchResult]:
        """The k Chunks nearest the query, nearest first."""
        (embedding,) = self._embedder.embed([query])
        where, params = _where(filter)
        rows = self._conn.execute(
            f"SELECT {_COLUMNS}, 1 - (c.embedding <=> %(q)s::vector) AS score"
            f" FROM chunks c JOIN documents d ON d.id = c.document_id{where}"
            " ORDER BY c.embedding <=> %(q)s::vector, c.id LIMIT %(k)s",
            {"q": to_pgvector(embedding), "k": k} | params,
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

    def search(self, query: str, k: int, filter: Filter | None = None) -> list[SearchResult]:
        """The k Chunks that best match the query's terms, best first; none share a term → []."""
        (terms,) = self._conn.execute(
            "SELECT array(SELECT lexeme FROM unnest(to_tsvector('english', %s)))", [query]
        ).fetchone()
        where, params = _where(filter)
        among = None
        if where:  # the index holds every Chunk, so the filter picks which ones it may return
            rows = self._conn.execute(
                f"SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id{where}", params
            ).fetchall()
            among = {chunk for (chunk,) in rows}
        top = self._index.top(terms, k, among)
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

    def search(self, query: str, k: int, filter: Filter | None = None) -> list[SearchResult]:
        """The k Chunks with the highest fused score, highest first."""
        depth = max(k, self._candidates)
        scores: dict[Chunk, float] = {}
        for searcher in self._searchers:
            for rank, result in enumerate(searcher.search(query, depth, filter), start=1):
                scores[result.chunk] = scores.get(result.chunk, 0.0) + 1 / (RRF_K + rank)
        top = sorted(scores.items(), key=lambda item: -item[1])[:k]
        return [SearchResult(chunk, score) for chunk, score in top]


class Scorer(Protocol):
    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        """One relevance score per (query, Chunk text) pair, in order; higher is more relevant."""
        ...


class RerankingSearcher:
    """Re-orders another Searcher's Chunks by a Scorer (a cross-encoder reads the query and each
    Chunk's text together): asks it for max(k, candidates) Chunks and keeps the top k."""

    def __init__(self, searcher: Searcher, scorer: Scorer, candidates: int):
        self._searcher = searcher
        self._scorer = scorer
        self._candidates = candidates

    def search(self, query: str, k: int, filter: Filter | None = None) -> list[SearchResult]:
        """The k best-scored Chunks, best first."""
        inner = self._searcher.search(query, max(k, self._candidates), filter)
        chunks = [r.chunk for r in inner]
        scores = self._scorer.score([(query, chunk.text) for chunk in chunks])
        ranked = sorted(zip(chunks, scores, strict=True), key=lambda item: -item[1])[:k]
        return [SearchResult(chunk, score) for chunk, score in ranked]


def _where(filter: Filter | None) -> tuple[str, dict]:
    """A WHERE clause matching the filter's set fields (named like the documents columns), or "",
    and its parameters."""
    fields = asdict(filter or Filter())
    params = {name: value for name, value in fields.items() if value is not None}
    clause = " AND ".join(f"d.{name} = %({name})s" for name in params)
    return (f" WHERE {clause}" if clause else ""), params


def _results(rows: list[tuple]) -> list[SearchResult]:
    results = []
    for name, company, doc_type, fiscal_year, page, position, text, token_count, score in rows:
        document = Document(name, company, doc_type, fiscal_year)
        chunk = Chunk(document, page, position, text, token_count)
        results.append(SearchResult(chunk, score))
    return results
