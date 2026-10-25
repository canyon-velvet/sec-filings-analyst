# 2. Contextual headers: fixed metadata, not LLM-written context

Date: 2026-10-25 · Status: accepted · Ticket: #32

## Context

A Chunk's text often doesn't say whose filing it is or which year: "Net sales increased 5%"
reads the same in every 10-K. Dense search then ranks other companies' and other years'
Chunks next to the right one. On dev, 123 of dense's 250 top-5 Pages come from Documents other
than the Question's, and filtering to the Question's own company, Doc type and Fiscal year lifts
Hit@5 from 0.40 to 0.60 (#31). Giving each Chunk its context before it is embedded attacks the
same problem without knowing the answer's Document.

## Decision

- **Header:** `{company} {doc_type} FY{fiscal_year}, page {page}`, from the Document's metadata,
  e.g. `3M 10-K FY2018, page 60`. It is embedded and keyword-indexed as the first line of the
  Chunk, and stored in its own column; the Chunk's stored text stays the Page's own, so Answers
  and Citations quote the Document, not the header.
- **"FY2018":** 34 of the 50 dev Questions write FY and four digits, and keyword search
  matches whole lexemes (`fy2018`). 4 more write `FY22` or `FY2023Q1` (lexemes `fy22`,
  `fy2023q1`) and 10 a bare year: those reach the header only through dense search.
- **Tokens:** the 512-token limit stays on the Page text; the header line (about 12–15 tokens)
  is extra: 0.35M tokens over today's 25,854 Chunks, ≈ $0.007 at $0.02 per million.
- **Corpus settings** record the header format, so runs before and after the re-ingest are
  distinguishable, and ingest refuses to mix headered and bare Chunks.

## Alternatives

- **LLM-written context** (e.g. Anthropic's Contextual Retrieval): a model reads the whole
  Document and writes a sentence or two placing each Chunk. A Document averages about 125k
  tokens (10.5M / 84), so 25,854 Chunks need about 3.2 billion input tokens: hundreds of dollars
  at a small model's list price of about $0.15 per million input tokens, cut by roughly half to
  90% with prompt caching, paid again on every re-ingest, and not deterministic. It can say more
  than metadata (the section, what a table is about); revisit if headers stop helping.
- **No header, filters only:** filters need the agent to know the company and year; most
  Questions name them, but a header also helps when the agent doesn't filter.

## Consequences

- Re-ingest #2 (`make db-reset` + `make ingest`, 10.8M tokens, about $0.22) replaces the
  corpus; earlier runs stay comparable through the corpus settings they record.
- The cross-encoder still reads only the stored text, so reranking doesn't see the header.
- Changing the format means another re-ingest.
