# SPEC: SEC Filings Analyst
Chat with an agent about any public company's SEC filings; answers cite their source.
Quality is proven by evals on FinanceBench. Portfolio project for AI-engineer roles.

## Scope
- In: multi-turn chat · multi-company comparisons via agent tools · cited answers · eval harness + ablations on FinanceBench ·
  any company's filing fetched from SEC EDGAR on demand (week 4)
- Out (for now): bulk pre-ingestion of many filings · user uploads · auth · nightly CI

## Stack
Python 3.12 + uv · FastAPI (SSE) · Postgres + pgvector (Docker, :5433) + Postgres FTS · pypdfium2 (PDF; HTML parser TBD in week 4) ·
OpenAI (text-embedding-3-small, pinned chat snapshot) · local cross-encoder reranker ·
Vite + React + TS · no LangChain/LlamaIndex

## Evaluation
- FinanceBench open sample: 150 Qs, 84 docs, 32 companies (HF PatronusAI/financebench, CC-BY-NC; PDFs not committed)
- Split: `eval/splits/financebench_v1.json`, 50 dev / 100 test, stratified by question_type, never regenerated. Tune on dev, report on test.
- Retrieval: Hit@1/5/10, Recall@10, MRR@10 over unique (document, page) vs evidence pages; overall + per question_type. Headline: Hit@5.
- Answers (week 2): LLM judge + numeric tolerance + faithfulness. Week 3: custom multi-company and multi-turn cases.

## Milestones
### Week 1: foundation & baseline (spec: "Ingestion + dense baseline retrieval eval")
- [x] Bootstrap repo (git, SPEC, CLAUDE.md)
- [x] Python skeleton + ruff lint hook + pre-push review gate
- [x] Postgres + pgvector via Docker; schema
- [x] Download FinanceBench + PDFs; dev/test split
- [x] Ingest: parse per page → page-bounded chunks (512/64 tok) → embed → store
- [x] Retrieval metrics (TDD) + dense-only baseline on dev: **Hit@5 = 0.40** (`eval/RESULTS.md`)
### Week 2: hybrid (RRF) · reranker · metadata filters · contextual headers · cited answers + answer evals (spec: #26)
- [x] Named Experiments; runs record commit, corpus counts, Questions under 10 Pages (#27)
- [x] Keyword search + hybrid RRF: dev Hit@5 0.10 (BM25), 0.26 (hybrid) vs dense 0.40 (#28, #29)
- [ ] Reranker (#30)
- [ ] Metadata filters + contextual headers (#31, #32)
- [ ] Cited Answers + answer evals (#33–#36)
- [ ] Judge validation + test-Split report (#37, #38)
### Week 3: agent tools (search, calculate) + loop · follow-ups · /chat SSE · chat UI (citations, agent-steps panel) · agent evals
### Week 4: EDGAR on-demand ingestion (ticker + form + year) · HTML parsing · section-based citations · fetch-filing agent tool
### Week 5: CI eval smoke · cost/latency · deploy · README results + demo

## Decisions (date · decision · why)
- 2026-10-14 · FinanceBench companies only (superseded 2026-10-15) · every answerable question is measurable
- 2026-10-14 · Hand-rolled agent tool loop · multi-company comparisons; shows fundamentals
- 2026-10-14 · pgvector in Docker on :5433 · reproducible; local PG14 lacks pgvector
- 2026-10-14 · Page-bounded chunks for PDFs (FinanceBench) · each chunk maps to one page → clean citations and metrics
- 2026-10-14 · Dev/test split · avoids overfitting the reported numbers
- 2026-10-14 · No nightly CI · nothing changes without a commit; model snapshots pinned
- 2026-10-14 · PRs ≤ ~200 lines + 3 reviews before push · easy review
- 2026-10-14 · pypdfium2 + MIT license · permissive end to end (pymupdf is AGPL)
- 2026-10-14 · Python at repo root · one project; simple commands, CI and hooks
- 2026-10-14 · Exact search, no ANN index in week 1 · keeps approximation noise out of the baseline
- 2026-10-15 · Code in `src/sec_filings_analyst/` (uv_build package) · imports don't depend on the cwd; `python -m` works
- 2026-10-15 · Push gate catches forgotten reviews, not evasion; GitHub ruleset guards main · parsing shell text can't be airtight
- 2026-10-15 · Cosine distance (`<=>`) for search · OpenAI recommends it; ranks like inner product on normalized vectors but stays correct for test vectors
- 2026-10-16 · Chunk tokens counted with cl100k_base (`encode_ordinary`) · same tokenizer as text-embedding-3-small, so counts match the embedder
- 2026-10-16 · Refuse PDFs without text (scans) · a missing Document would silently lower retrieval scores
- 2026-10-16 · FinanceBench pinned: HF dataset revision + PDFs from its GitHub repo at a fixed commit · every run scores the same inputs
- 2026-10-19 · FinanceBench `evidence_page_num` is 0-based; `load_questions` adds 1 · all 189 full-page evidence texts match our parsed Page at num + 1 (≥ 0.95 similarity), none at num
- 2026-10-19 · Embeddings requested 256 texts at a time · stays under OpenAI's 300k-tokens-per-request cap with 512-token Chunks
- 2026-10-19 · `make ingest` shows tokens + estimated cost and asks before any embedding request · money is never spent by accident
- 2026-10-19 · Ingest skips Documents already stored (by name), one transaction each · a rerun resumes without paying twice; after a chunking change, `make db-reset` first
- 2026-10-19 · `CHECK` on `documents.doc_type` (10-K, 10-Q, 8-K, Earnings) · a value that skipped normalization fails loudly
- 2026-10-19 · Eval fetches 50 Chunks per Question · several Chunks share a Page, and @10 metrics need 10 unique Pages
- 2026-10-19 · One results file per (Split, experiment), never overwritten; `eval/RESULTS.md` regenerated from all of them · reported numbers can't silently change
- 2026-10-15 · Any company via EDGAR on demand (built week 4, deployed week 5); FinanceBench stays the eval set · goal is answering questions on any filing; the benchmark proves the pipeline
- 2026-10-21 · Experiments are named in code (name → Searcher stack + settings); unknown names refused · one entry holds both the stack and the settings its runs record, not hand-built config in the entry point
- 2026-10-21 · Run files written to a temp file, then hard-linked into place · a crashed or killed run leaves no half file (no fsync), and a run still can't be overwritten
- 2026-10-22 · Corpus settings (embedding model, chunk + overlap tokens) stored with the first Document; ingest refuses Chunks made differently; runs copy them · a run describes the corpus it searched, not today's code constants (header format joins in #32)
- 2026-10-22 · Keyword search: BM25 (k1 1.2, b 0.75) in Python over Postgres 'english' lexemes, any shared term · Postgres `ts_rank_cd` has no IDF: dev Hit@5 0.02, subsidiary lists repeating "company" ranked first
- 2026-10-23 · Hybrid = RRF (k 60) over 100 candidates per Searcher; ties keep the earlier (dense) list's order · on dev it loses to dense (Hit@5 0.26 vs 0.40): any Chunk both lists rank beats a dense-only rank 1, and BM25's wrong Pages win; #30 reranks dense

## Open questions
- None

## Progress log
- 2026-10-14 · Repo bootstrapped
- 2026-10-14 · README (problem + planned approach) added
- 2026-10-15 · Scope widened to any company via EDGAR; week-1 spec published as issue #2
- 2026-10-15 · uv skeleton, CI (lint + unit tests), ruff lint hook (#4, part 1; push gate next)
- 2026-10-15 · Push gate hook (no main, reviewed HEAD, no merged-PR branches); `env.example` rename (#4)
- 2026-10-15 · Postgres + pgvector (Docker :5433), `make db-up` / `make db-reset`, documents + chunks schema (#5)
- 2026-10-15 · Tracer bullet: fixture PDF → pypdfium2 Pages → fake Embedder → Postgres → `Retriever.search`; GLOSSARY.md (#6)
- 2026-10-16 · Page-bounded chunking, 512 tokens with 64 overlap (cl100k_base); text-less PDFs refused (#7)
- 2026-10-16 · Retrieval scoring: `score()` → Hit@1/5/10, Recall@10, MRR@10 per Question, per type, overall (#8)
- 2026-10-16 · `make data`: FinanceBench Questions (Doc types normalized, e.g. 10k → 10-K) + 84 PDFs, pinned (#9, part 1)
- 2026-10-16 · `make split`: `eval/splits/financebench_v1.json`, 50 dev (17/17/16 by type) / 100 test, seed 2026 (#9)
- 2026-10-19 · Evidence pages aligned to 1-based Pages; local check on 20 sampled Questions vs FinanceBench's full-page text (#10)
- 2026-10-19 · `OpenAIEmbedder` (text-embedding-3-small, batches of 256, injected client; fake client for tests) (#11, part 1)
- 2026-10-19 · `make ingest`: cost prompt before any API call, resumable; 84 Documents, 25,854 Chunks, 10.5M tokens (≈ $0.21) stored; Doc type CHECK (#11)
- 2026-10-19 · `make eval`: dense-only baseline on dev, Hit@5 0.40 · MRR@10 0.24; 27 of 30 misses retrieve the right Document but the wrong Page (#12)
- 2026-10-20 · Week-2 spec #26 and tickets #27–#38
- 2026-10-21 · `make eval EXPERIMENT=` builds a named Experiment; runs record commit, Document/Chunk counts, Questions under 10 Pages; atomic UTF-8 writes (#27)
- 2026-10-22 · Corpus settings in the database; ingest refuses mixed settings; runs read them from the database; re-ingest #1 (#28, part 1)
- 2026-10-22 · `keyword-bm25` on dev: Hit@5 0.10 · MRR@10 0.11 (dense 0.40 · 0.24); right company, wrong year or Page; only 2 Questions in the top 10 by keyword but not dense (#28)
- 2026-10-23 · `hybrid-rrf` on dev: Hit@5 0.26 · MRR@10 0.18; 4 Questions gained, 11 lost from dense's top 5; evidence in the 50 Chunks for 34 Questions (dense 40) (#29)

## How to resume
1. Read this file, `git log --oneline -20` and the open `ready-for-agent` issues. 2. Take the first unchecked task.
3. If it touches an open question, grill the user first; feature specs come from `/to-spec`. 4. Update this file in the same PR.
