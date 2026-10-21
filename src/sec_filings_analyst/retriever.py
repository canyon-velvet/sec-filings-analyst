"""Searchers: the top-k Chunks for a query. Evaluation and the agent both search through them."""

from dataclasses import dataclass

import psycopg

from sec_filings_analyst.documents import Chunk, Document
from sec_filings_analyst.embedder import Embedder, to_pgvector


@dataclass(frozen=True)
class SearchResult:
    chunk: Chunk
    score: float  # higher is closer; the scale depends on the Searcher (e.g. cosine, text rank)


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
    """Postgres full-text search: Chunks that share any term with the query (stemmed, without
    stopwords), ranked by ts_rank_cd. Terms are OR-ed: AND-ing every word of a long Question
    would match almost nothing. Needs an autocommit connection, like Retriever."""

    def __init__(self, conn: psycopg.Connection):
        self._conn = conn

    def search(self, query: str, k: int) -> list[SearchResult]:
        """The k Chunks that best match the query's terms, best first; none share a term → []."""
        rows = self._conn.execute(
            f"SELECT {_COLUMNS}, ts_rank_cd(c.tsv, q) AS score"
            " FROM chunks c JOIN documents d ON d.id = c.document_id,"
            # plainto_tsquery joins the lexemes with &; | makes any one of them enough
            " (SELECT replace(plainto_tsquery('english', %(query)s)::text, '&', '|')::tsquery"
            " AS q) t"
            " WHERE c.tsv @@ q ORDER BY score DESC, c.id LIMIT %(k)s",
            {"query": query, "k": k},
        ).fetchall()
        return _results(rows)


def _results(rows: list[tuple]) -> list[SearchResult]:
    results = []
    for name, company, doc_type, fiscal_year, page, position, text, token_count, score in rows:
        document = Document(name, company, doc_type, fiscal_year)
        chunk = Chunk(document, page, position, text, token_count)
        results.append(SearchResult(chunk, score))
    return results
