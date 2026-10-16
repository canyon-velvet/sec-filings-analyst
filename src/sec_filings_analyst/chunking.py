"""Parse-and-chunk: a PDF becomes Page-bounded Chunks of at most 512 tokens, overlapping by 64."""

from contextlib import closing
from pathlib import Path
from typing import Protocol

import pypdfium2
import tiktoken

from sec_filings_analyst.documents import Chunk, Document

CHUNK_TOKENS = 512
OVERLAP_TOKENS = 64


class Tokenizer(Protocol):
    """Counts tokens like the embedding model."""

    def encode(self, text: str) -> list[int]: ...

    def decode(self, tokens: list[int]) -> str: ...


class Cl100kTokenizer:
    """text-embedding-3-small's tokenizer. First use downloads its vocabulary once."""

    def __init__(self):
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def encode(self, text: str) -> list[int]:
        # Plain encode() raises on text such as "<|endoftext|>"; a filing's text is never special.
        return self._encoding.encode_ordinary(text)

    def decode(self, tokens: list[int]) -> str:
        return self._encoding.decode(tokens)


def parse_pages(pdf: Path) -> list[str]:
    """Text of each Page; Page n is at index n - 1."""
    texts = []
    with pypdfium2.PdfDocument(pdf) as document:
        for page in document:  # close each Page as we go: 10-Ks run to hundreds of Pages
            # PdfPage and PdfTextPage have close() but aren't context managers.
            with closing(page), closing(page.get_textpage()) as textpage:
                texts.append(textpage.get_text_range())
    return texts


def chunk_pages(pages: list[str], document: Document, tokenizer: Tokenizer) -> list[Chunk]:
    """Chunks in Page order, from parse_pages' output; a Chunk never spans two Pages, and empty
    Pages give none."""
    chunks = []
    for page, text in enumerate(pages, start=1):
        if not text.strip():
            continue
        tokens = tokenizer.encode(text)
        for position, start in enumerate(range(0, len(tokens), CHUNK_TOKENS - OVERLAP_TOKENS)):
            window = tokens[start : start + CHUNK_TOKENS]
            chunks.append(Chunk(document, page, position, tokenizer.decode(window), len(window)))
            if start + CHUNK_TOKENS >= len(tokens):
                break
    return chunks
