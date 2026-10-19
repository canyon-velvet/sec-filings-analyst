"""Ingestion: parse and chunk Documents, confirm the embedding cost, embed and store them."""

import os
from collections.abc import Callable
from pathlib import Path

import psycopg

from sec_filings_analyst.chunking import Cl100kTokenizer, chunk_pages, parse_pages
from sec_filings_analyst.documents import Chunk, Document
from sec_filings_analyst.embedder import (
    PRICE_PER_MILLION_TOKENS,
    Embedder,
    OpenAIEmbedder,
    to_pgvector,
)
from sec_filings_analyst.financebench import load_questions


def ingest(
    pdfs: dict[Document, Path],
    embedder: Embedder,
    conn: psycopg.Connection,
    confirm: Callable[[str], bool],
) -> None:
    """Parses and chunks every Document not stored yet, then asks confirm() about the token
    count and estimated cost before embedding anything; declining embeds and stores nothing.
    Each Document is stored with its Chunks in one committed transaction, so a rerun resumes
    an interrupted one.

    Needs an autocommit connection: otherwise an open transaction would turn this into an
    uncommitted savepoint. Raises RuntimeError if the schema is missing (it never creates
    it: db/schema.sql drops every table first), and ValueError for a PDF without
    text (e.g. a scan), so a missing Document can't silently lower retrieval scores."""
    if not conn.autocommit:
        raise ValueError("ingest needs an autocommit connection, or nothing may be committed")
    try:
        stored = {name for (name,) in conn.execute("SELECT name FROM documents")}
    except psycopg.errors.UndefinedTable:
        raise RuntimeError("no documents table: run `make db-reset` to create the schema") from None
    tokenizer = Cl100kTokenizer()
    pending: dict[Document, tuple[int, list[Chunk]]] = {}  # Document → (page count, Chunks)
    for document, pdf in pdfs.items():
        if document.name in stored:
            continue
        print(f"Parsing {document.name}")
        pages = parse_pages(pdf)
        chunks = chunk_pages(pages, document, tokenizer)
        if not chunks:
            raise ValueError(
                f"{document.name}: no text in {pdf}; is it a scan without a text layer?"
            )
        pending[document] = (len(pages), chunks)
    all_chunks = [chunk for _, chunks in pending.values() for chunk in chunks]
    tokens = sum(chunk.token_count for chunk in all_chunks)
    cost = tokens / 1_000_000 * PRICE_PER_MILLION_TOKENS
    summary = (
        f"Documents: {len(pending)}, Chunks: {len(all_chunks):,}, tokens: {tokens:,},"
        f" estimated cost: ${cost:.4f}"
    )
    if not confirm(summary):
        return
    for document, (page_count, chunks) in pending.items():
        print(f"Embedding {document.name} ({len(chunks)} Chunks)")
        _store(document, page_count, chunks, embedder.embed([c.text for c in chunks]), conn)


def _store(
    document: Document,
    page_count: int,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    conn: psycopg.Connection,
) -> None:
    with conn.transaction():
        (document_id,) = conn.execute(
            "INSERT INTO documents (name, company, doc_type, fiscal_year, page_count)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            [document.name, document.company, document.doc_type, document.fiscal_year, page_count],
        ).fetchone()
        conn.cursor().executemany(
            "INSERT INTO chunks (document_id, page, position, text, token_count, embedding)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [
                [document_id, c.page, c.position, c.text, c.token_count, to_pgvector(embedding)]
                for c, embedding in zip(chunks, embeddings, strict=True)
            ],
        )


def _ask(summary: str) -> bool:
    return input(f"Embed {summary}? [y/N] ").strip().lower() == "y"


if __name__ == "__main__":
    import openai  # here, so importing this module doesn't load the SDK (see embedder.py)

    data = Path("data/financebench")
    questions = load_questions(data / "financebench_merged.jsonl")
    pdfs = {q.document: data / "pdfs" / f"{q.document.name}.pdf" for q in questions}
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        ingest(pdfs, OpenAIEmbedder(openai.OpenAI()), conn, _ask)
