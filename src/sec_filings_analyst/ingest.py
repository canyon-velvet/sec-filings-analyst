"""Ingestion: parse and chunk Documents, confirm the embedding cost, embed and store them."""

import os
from collections.abc import Callable
from pathlib import Path

import psycopg

from sec_filings_analyst.chunking import (
    CHUNK_TOKENS,
    HEADER_FORMAT,
    OVERLAP_TOKENS,
    Cl100kTokenizer,
    chunk_pages,
    contextual_header,
    parse_pages,
)
from sec_filings_analyst.documents import Chunk, Document
from sec_filings_analyst.embedder import (
    PRICE_PER_MILLION_TOKENS,
    Embedder,
    OpenAIEmbedder,
    to_pgvector,
)
from sec_filings_analyst.financebench import load_questions

_SETTINGS = "embedding_model, chunk_tokens, overlap_tokens, header_format"
# A table or a column the schema doesn't have yet (e.g. from before Contextual headers)
_OUTDATED_SCHEMA = (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn)


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
    uncommitted savepoint. Raises RuntimeError, before parsing anything, if the schema is
    missing (it never creates it: db/schema.sql drops every table first) or the stored Chunks
    were made with other settings (embedding model, chunk tokens, overlap, header format), so
    one corpus never mixes two kinds of Chunks. Raises ValueError for a PDF without text (e.g. a
    scan), so a missing Document can't silently lower retrieval scores."""
    if not conn.autocommit:
        raise ValueError("ingest needs an autocommit connection, or nothing may be committed")
    try:
        stored = {name for (name,) in conn.execute("SELECT name FROM documents")}
        made_with = conn.execute(f"SELECT {_SETTINGS} FROM corpus_settings").fetchone()
        # None until the first Document is stored
    except _OUTDATED_SCHEMA:
        raise RuntimeError("schema missing or out of date: run `make db-reset`") from None
    settings = (embedder.model, CHUNK_TOKENS, OVERLAP_TOKENS, HEADER_FORMAT)
    if made_with is not None and made_with != settings:
        raise RuntimeError(
            f"stored Chunks were made with {made_with}, not {settings}:"
            " run `make db-reset` to re-ingest everything"
        )
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
    # Each Chunk's header line is embedded, and paid for, on top of its Page text
    headers = sum(len(tokenizer.encode(f"{contextual_header(c)}\n")) for c in all_chunks)
    tokens = sum(chunk.token_count for chunk in all_chunks) + headers
    cost = tokens / 1_000_000 * PRICE_PER_MILLION_TOKENS
    summary = (
        f"Documents: {len(pending)}, Chunks: {len(all_chunks):,}, tokens: {tokens:,},"
        f" estimated cost: ${cost:.4f}"
    )
    if not confirm(summary):
        return
    for document, (page_count, chunks) in pending.items():
        print(f"Embedding {document.name} ({len(chunks)} Chunks)")
        embeddings = embedder.embed([f"{contextual_header(c)}\n{c.text}" for c in chunks])
        _store(document, page_count, chunks, embeddings, embedder.model, conn)


def describe_corpus(conn: psycopg.Connection) -> dict:
    """What is stored, for a run to record: Document and Chunk counts, and how the Chunks were
    made. Raises RuntimeError if no ingest recorded that (nothing ingested yet, or a schema
    from before corpus settings or Contextual headers)."""
    try:
        settings = conn.execute(f"SELECT {_SETTINGS} FROM corpus_settings").fetchone()
    except _OUTDATED_SCHEMA:
        settings = None
    if settings is None:
        raise RuntimeError("no corpus settings: run `make db-reset`, then `make ingest`")
    embedding_model, chunk_tokens, overlap_tokens, header_format = settings
    (documents,) = conn.execute("SELECT count(*) FROM documents").fetchone()
    (chunks,) = conn.execute("SELECT count(*) FROM chunks").fetchone()
    return {
        "documents": documents,
        "chunks": chunks,
        "embedding_model": embedding_model,
        "chunk_tokens": chunk_tokens,
        "overlap_tokens": overlap_tokens,
        "header_format": header_format,
    }


def _store(
    document: Document,
    page_count: int,
    chunks: list[Chunk],
    embeddings: list[list[float]],
    embedding_model: str,
    conn: psycopg.Connection,
) -> None:
    with conn.transaction():
        # With the first Document, so corpus settings never exist without stored Chunks
        conn.execute(
            f"INSERT INTO corpus_settings ({_SETTINGS})"
            " VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",  # later Documents keep the first row
            [embedding_model, CHUNK_TOKENS, OVERLAP_TOKENS, HEADER_FORMAT],
        )
        (document_id,) = conn.execute(
            "INSERT INTO documents (name, company, doc_type, fiscal_year, page_count)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            [document.name, document.company, document.doc_type, document.fiscal_year, page_count],
        ).fetchone()
        conn.cursor().executemany(
            "INSERT INTO chunks"
            " (document_id, page, position, header, text, token_count, embedding)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                [document_id, c.page, c.position, contextual_header(c), c.text, c.token_count]
                + [to_pgvector(embedding)]
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
