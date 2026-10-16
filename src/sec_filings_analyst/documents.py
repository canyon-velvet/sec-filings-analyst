"""Document: one company report and its metadata, whatever format it came in."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Document:
    name: str  # FinanceBench doc_name, e.g. 3M_2018_10K
    company: str
    doc_type: str  # 10-K, 10-Q, 8-K, Earnings
    fiscal_year: int
