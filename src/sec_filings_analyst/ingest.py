"""Ingestion: parse a PDF Page by Page, embed one Chunk per Page, store the Document and Chunks."""

from pathlib import Path

import psycopg
import pypdfium2

from sec_filings_analyst.documents import Document
from sec_filings_analyst.embedder import Embedder, to_pgvector


def parse_pages(pdf: Path) -> list[str]:
    """Text of each Page; Page n is at index n - 1."""
    document = pypdfium2.PdfDocument(pdf)
    try:
        return [page.get_textpage().get_text_range() for page in document]
    finally:
        document.close()


def ingest(pdf: Path, document: Document, embedder: Embedder, conn: psycopg.Connection) -> None:
    """Stores the Document and its Chunks in one committed transaction.

    Needs an autocommit connection: otherwise an open transaction would turn this into an
    uncommitted savepoint. Expects the schema to exist."""
    if not conn.autocommit:
        raise ValueError("ingest needs an autocommit connection, or nothing may be committed")
    pages = parse_pages(pdf)
    # Placeholder chunking until #7: one Chunk per non-empty Page.
    chunks = [(number, text) for number, text in enumerate(pages, start=1) if text.strip()]
    embeddings = embedder.embed([text for _, text in chunks])
    with conn.transaction():
        (document_id,) = conn.execute(
            "INSERT INTO documents (name, company, doc_type, fiscal_year, page_count)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            [document.name, document.company, document.doc_type, document.fiscal_year, len(pages)],
        ).fetchone()
        conn.cursor().executemany(
            "INSERT INTO chunks (document_id, page, position, text, token_count, embedding)"
            " VALUES (%s, %s, 0, %s, %s, %s)",
            # Placeholder token count (words) until #7 counts the embedding model's tokens.
            [
                [document_id, page, text, len(text.split()), to_pgvector(embedding)]
                for (page, text), embedding in zip(chunks, embeddings, strict=True)
            ],
        )
