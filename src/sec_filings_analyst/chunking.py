"""Parse-and-chunk: a PDF becomes Page-bounded Chunks of at most 512 tokens, overlapping by 64."""

from pathlib import Path
from typing import Protocol

import pypdfium2

from sec_filings_analyst.documents import Chunk, Document

CHUNK_TOKENS = 512
OVERLAP_TOKENS = 64


class Tokenizer(Protocol):
    """Counts tokens like the embedding model; tiktoken's cl100k_base fits as is."""

    def encode(self, text: str) -> list[int]: ...

    def decode(self, tokens: list[int]) -> str: ...


def parse_pages(pdf: Path) -> list[str]:
    """Text of each Page; Page n is at index n - 1."""
    document = pypdfium2.PdfDocument(pdf)
    try:
        texts = []
        for page in document:  # close each Page as we go: 10-Ks run to hundreds of Pages
            textpage = page.get_textpage()
            texts.append(textpage.get_text_range())
            textpage.close()
            page.close()
        return texts
    finally:
        document.close()


def count_pages(pdf: Path) -> int:
    """Reads only the page tree, not the text."""
    document = pypdfium2.PdfDocument(pdf)
    try:
        return len(document)
    finally:
        document.close()


def chunk_pdf(pdf: Path, document: Document, tokenizer: Tokenizer) -> list[Chunk]:
    """Chunks in Page order; a Chunk never spans two Pages, and empty Pages give none."""
    chunks = []
    for page, text in enumerate(parse_pages(pdf), start=1):
        if not text.strip():
            continue
        tokens = tokenizer.encode(text)
        for position, start in enumerate(range(0, len(tokens), CHUNK_TOKENS - OVERLAP_TOKENS)):
            window = tokens[start : start + CHUNK_TOKENS]
            chunks.append(Chunk(document, page, position, tokenizer.decode(window), len(window)))
            if start + CHUNK_TOKENS >= len(tokens):
                break
    return chunks
