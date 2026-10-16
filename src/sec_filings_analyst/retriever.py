"""Retriever: the top-k Chunks for a query. Evaluation and the agent both search through it."""

from dataclasses import dataclass

import psycopg

from sec_filings_analyst.documents import Document
from sec_filings_analyst.embedder import Embedder, to_pgvector


@dataclass(frozen=True)
class Chunk:
    document: Document
    page: int  # 1-based
    text: str
    score: float  # cosine similarity to the query; higher is closer


class Retriever:
    """Dense-only, exact (no approximate index) cosine search over every stored Chunk.

    Needs an autocommit connection, so searches never hold a transaction open."""

    def __init__(self, conn: psycopg.Connection, embedder: Embedder):
        self._conn = conn
        self._embedder = embedder

    def search(self, query: str, k: int) -> list[Chunk]:
        """The k Chunks nearest the query, nearest first."""
        (embedding,) = self._embedder.embed([query])
        rows = self._conn.execute(
            "SELECT d.name, d.company, d.doc_type, d.fiscal_year, c.page, c.text,"
            " 1 - (c.embedding <=> %(q)s::vector) AS score"
            " FROM chunks c JOIN documents d ON d.id = c.document_id"
            " ORDER BY c.embedding <=> %(q)s::vector, c.id LIMIT %(k)s",
            {"q": to_pgvector(embedding), "k": k},
        ).fetchall()
        return [
            Chunk(Document(name, company, doc_type, year), page, text, score)
            for name, company, doc_type, year, page, text, score in rows
        ]
