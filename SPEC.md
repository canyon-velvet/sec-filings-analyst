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
### Week 2: hybrid (RRF) · reranker · metadata filters · contextual headers · cited answers + answer evals
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

## How to resume
1. Read this file, `git log --oneline -20` and the open `ready-for-agent` issues. 2. Take the first unchecked task.
3. If it touches an open question, grill the user first; feature specs come from `/to-spec`. 4. Update this file in the same PR.
