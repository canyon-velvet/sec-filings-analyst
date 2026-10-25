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
A span of text from exactly one Page, at most 512 tokens, stored with its embedding.
A Searcher returns Chunks ranked by how well they match the query, each with its score.
_Avoid_: passage, snippet, segment

**Corpus settings**:
How every stored Chunk was made: embedding model, chunk tokens, overlap. Stored once in the database; a corpus never mixes two.
_Avoid_: config, ingest settings

**Searcher**:
Anything that returns the top-k Chunks for a query: dense (the Retriever, by embedding), keyword (BM25 over the Chunk's terms), hybrid (other Searchers' rankings fused with RRF), or reranking (another Searcher's Chunks re-ordered by a cross-encoder).
_Avoid_: retriever (that's the dense one), engine

**Filter**:
Which Documents a search may return Chunks from, by company, Doc type and Fiscal year (each optional). An oracle filter is a Question's Document's company, Doc type and Fiscal year, which only an eval knows (two 8-Ks can share them).
_Avoid_: where clause, scope

### Evaluation

**Question**:
One FinanceBench question with its answer, question type and Evidence pages.
_Avoid_: query (the text sent to a Searcher), sample

**Evidence page**:
A Page that FinanceBench marks as containing the evidence for a Question's answer.
_Avoid_: gold page, ground truth

**Experiment**:
A named retrieval setup: which Searcher stack is built and with which settings, e.g. `dense-baseline`.
Tuned on dev, then reported on test under the same name.
_Avoid_: config, variant

**Run**:
One Experiment scored on one Split, saved once and never overwritten, with the commit and the corpus (counts + Corpus settings) it ran against.
_Avoid_: result, job

**Split**:
A committed, versioned partition of Questions into dev (tuning) and test (reporting).
_Avoid_: fold
