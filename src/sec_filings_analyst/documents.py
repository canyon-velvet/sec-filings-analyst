"""Document and Chunk: what gets stored and searched, whatever format the Document came in."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    name: str  # FinanceBench doc_name, e.g. 3M_2018_10K
    company: str
    doc_type: str  # 10-K, 10-Q, 8-K, Earnings
    fiscal_year: int


@dataclass(frozen=True)
class Chunk:
    document: Document
    page: int  # 1-based
    position: int  # order within the Page, from 0
    text: str
    token_count: int  # in the embedding model's tokenizer
