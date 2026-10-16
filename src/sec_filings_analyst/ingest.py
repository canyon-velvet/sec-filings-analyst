"""Ingestion: chunk a PDF, embed the Chunks, store the Document and Chunks."""

from pathlib import Path

import psycopg
import tiktoken

from sec_filings_analyst.chunking import chunk_pdf, count_pages
from sec_filings_analyst.documents import Document
from sec_filings_analyst.embedder import Embedder, to_pgvector


def ingest(pdf: Path, document: Document, embedder: Embedder, conn: psycopg.Connection) -> None:
    """Stores the Document and its Chunks in one committed transaction.

    Needs an autocommit connection: otherwise an open transaction would turn this into an
    uncommitted savepoint. Expects the schema to exist. Raises ValueError for a PDF without
    text (e.g. a scan), so a missing Document can't silently lower retrieval scores."""
    if not conn.autocommit:
        raise ValueError("ingest needs an autocommit connection, or nothing may be committed")
    # cl100k_base is text-embedding-3-small's tokenizer; first use downloads it once.
    chunks = chunk_pdf(pdf, document, tiktoken.get_encoding("cl100k_base"))
    if not chunks:
        raise ValueError(f"{document.name}: no text in {pdf}; is it a scan without a text layer?")
    embeddings = embedder.embed([chunk.text for chunk in chunks])
    with conn.transaction():
        (document_id,) = conn.execute(
            "INSERT INTO documents (name, company, doc_type, fiscal_year, page_count)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            [
                document.name,
                document.company,
                document.doc_type,
                document.fiscal_year,
                count_pages(pdf),
            ],
        ).fetchone()
        conn.cursor().executemany(
            "INSERT INTO chunks (document_id, page, position, text, token_count, embedding)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [
                [document_id, c.page, c.position, c.text, c.token_count, to_pgvector(embedding)]
                for c, embedding in zip(chunks, embeddings, strict=True)
            ],
        )
