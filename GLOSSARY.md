# SEC Filings Analyst

Answers finance questions about companies' documents with Page-level citations, and measures retrieval against FinanceBench.

## Language

### Corpus

**Document**:
One company report as a single file, e.g. 3M's 2018 10-K. Named by its FinanceBench doc_name (`3M_2018_10K`).
_Avoid_: filing (Earnings documents aren't SEC filings), file, report

**Doc type**:
The kind of Document: `10-K`, `10-Q`, `8-K` or `Earnings`.
_Avoid_: form, filing type

**Fiscal year**:
The company's fiscal year the Document covers, as an integer (2018).
_Avoid_: year, period

**Page**:
One page of a Document, numbered from 1 as a person reads the PDF.
_Avoid_: page index (0-based)

**Chunk**:
A span of text from exactly one Page, stored with its embedding; the unit the Retriever returns.
_Avoid_: passage, snippet, segment

### Evaluation

**Question**:
One FinanceBench question with its answer, question type and Evidence pages.
_Avoid_: query (the text sent to the Retriever), sample

**Evidence page**:
A Page that FinanceBench marks as containing the evidence for a Question's answer.
_Avoid_: gold page, ground truth

**Split**:
A committed, versioned partition of Questions into dev (tuning) and test (reporting).
_Avoid_: fold
