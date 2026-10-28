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

**Contextual header**:
One line made from a Chunk's Document and Page (`3M 10-K FY2018, page 60`), embedded and keyword-indexed with the Chunk but not part of its stored text.
_Avoid_: prefix, context, title

**Corpus settings**:
How every stored Chunk was made: embedding model, chunk tokens, overlap, Contextual header format. Stored once in the database; a corpus never mixes two.
_Avoid_: config, ingest settings

**Searcher**:
Anything that returns the top-k Chunks for a query: dense (the Retriever, by embedding), keyword (BM25 over the Chunk's terms), hybrid (other Searchers' rankings fused with RRF), or reranking (another Searcher's Chunks re-ordered by a cross-encoder).
_Avoid_: retriever (that's the dense one), engine

**Filter**:
Which Documents a search may return Chunks from, by company, Doc type and Fiscal year (each optional). An oracle filter is a Question's Document's company, Doc type and Fiscal year, which only an eval knows (two 8-Ks can share them).
_Avoid_: where clause, scope

### Answers

**Answer**:
Text an Answerer writes for a Question from the Chunks it is given, with inline markers ([2]) for its Citations; it says it can't find the answer when the Chunks don't contain it.
_Avoid_: response, completion, reply

**Citation**:
A marker in an Answer pointing to one of the Chunks the Answerer was given, so to a (Document, Page). A marker matching no given Chunk is an invalid citation: dropped and counted.
_Avoid_: source, reference

**Numeric check**:
For a Question whose FinanceBench answer is a single number (a numeric Question), whether the Answer states that number within 1%; a rule in code that cross-checks the Judge.
_Avoid_: exact match, numeric accuracy (that's the share of numeric Questions that pass)

**Judge**:
An LLM that grades each Answer twice: its correctness against FinanceBench's answer (correct, incorrect or refused) and its faithfulness to the Chunks it cites (supported or not supported).
_Avoid_: grader, evaluator

**Verdict**:
One of the Judge's grades: a label and a one-sentence reason. Unjudged when the Judge's reply held no label. The reason can restate FinanceBench's answer, so it is never committed.
_Avoid_: score, rating

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
One Experiment scored on one Split, for retrieval or for its Answers (an answer run), saved once and never overwritten, with the commit and the corpus (counts + Corpus settings) it ran against.
_Avoid_: result, job

**Split**:
A committed, versioned partition of Questions into dev (tuning) and test (reporting).
_Avoid_: fold
