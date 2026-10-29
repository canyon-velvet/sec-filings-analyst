# SPEC: SEC Filings Analyst
Chat with an agent about any public company's SEC filings; answers cite their source.
Quality is proven by evals on FinanceBench. Portfolio project for AI-engineer roles.

## Scope
- In: multi-turn chat · multi-company comparisons via agent tools · cited answers · eval harness + ablations on FinanceBench ·
  any company's filing fetched from SEC EDGAR on demand (week 4)
- Out (for now): bulk pre-ingestion of many filings · user uploads · auth · nightly CI

## Stack
Python 3.12 + uv · FastAPI (SSE) · Postgres + pgvector (Docker, :5433) + Postgres FTS · pypdfium2 (PDF; HTML parser TBD in week 4) ·
OpenAI (text-embedding-3-small, gpt-5.4-mini-2026-03-17 answers) · local cross-encoder reranker ·
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
- [x] Reranker: dev Hit@5 0.32 (50 candidates), 0.30 (100) vs dense 0.40 (#30)
- [x] Metadata filters + contextual headers: dev Hit@5 0.60 with oracle filters (an upper bound), 0.54 with headers, vs dense 0.40 (#31, #32)
- [x] Cited Answers + answer evals: dev accuracy 0.60 with `dense-headers` vs 0.30 with `keyword-bm25-headers` (#33–#36)
- [ ] Judge validation + test-Split report (#37 in progress: blind grading sheet; #38)
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
- 2026-10-19 · `make ingest` shows tokens + estimated cost and asks before any embedding request; `make answer-eval` shows a cost ceiling (Chunks at 512 tokens, Answers capped at 1,000) · money is never spent by accident
- 2026-10-19 · Ingest skips Documents already stored (by name), one transaction each · a rerun resumes without paying twice; after a chunking change, `make db-reset` first
- 2026-10-19 · `CHECK` on `documents.doc_type` (10-K, 10-Q, 8-K, Earnings) · a value that skipped normalization fails loudly
- 2026-10-19 · Eval fetches 50 Chunks per Question · several Chunks share a Page, and @10 metrics need 10 unique Pages
- 2026-10-19 · One results file per (Split, experiment), never overwritten; `eval/RESULTS.md` regenerated from all of them; answer runs commit no Answer text (it goes to a gitignored `.local.jsonl` beside the run) · reported numbers can't silently change; Answers can restate FinanceBench (CC-BY-NC)
- 2026-10-15 · Any company via EDGAR on demand (built week 4, deployed week 5); FinanceBench stays the eval set · goal is answering questions on any filing; the benchmark proves the pipeline
- 2026-10-21 · Experiments are named in code (name → Searcher stack + settings); unknown names refused · one entry holds both the stack and the settings its runs record, not hand-built config in the entry point
- 2026-10-21 · Run files written to a temp file, then hard-linked into place · a crashed or killed run leaves no half file (no fsync), and a run still can't be overwritten
- 2026-10-22 · Corpus settings (embedding model, chunk + overlap tokens) stored with the first Document; ingest refuses Chunks made differently; runs copy them · a run describes the corpus it searched, not today's code constants; the header format too since #32
- 2026-10-22 · Keyword search: BM25 (k1 1.2, b 0.75) in Python over Postgres 'english' lexemes, any shared term · Postgres `ts_rank_cd` has no IDF: dev Hit@5 0.02, subsidiary lists repeating "company" ranked first
- 2026-10-23 · Hybrid = RRF (k 60) over max(k, 100) candidates per Searcher; ties keep the earlier (dense) list's order · on dev it loses to dense (Hit@5 0.26 vs 0.40): a Chunk both lists rank in their top ~60 beats a dense-only rank 1, so BM25's wrong Pages win; #30 reranks dense
- 2026-10-23 · Reranker: local cross-encoder ms-marco-MiniLM-L6-v2 (Apache-2.0, pinned) on ONNX Runtime, CPU; libraries in a `rerank` group CI skips · torch has no Intel-Mac wheels; see docs/adr/0001. Both rerank runs lose to plain dense on dev, so `dense-baseline` stays the default Searcher
- 2026-10-24 · Filter (company, Doc type, Fiscal year; each optional) applied before the top-k cut: dense in its SQL, keyword ranks only the Chunks SQL matches; hybrid and reranking pass it on · cutting first would leave few Chunks. Oracle filters lift dev Hit@5 to 0.60 (dense 0.40): half of dense's top-5 Pages are other Documents', so the week-3 agent should filter
- 2026-10-25 · Contextual header `{company} {doc_type} FY{fiscal_year}, page {page}` embedded and keyword-indexed with each Chunk, not stored in its text; no LLM · ≈ $0.007 of tokens vs hundreds of dollars for LLM-written context (docs/adr/0002); dev Hit@5 0.54 vs 0.40, so dense on the headered corpus (`dense-headers`) is now the default Searcher
- 2026-10-25 · Answerer: gpt-5.4-mini-2026-03-17 (Chat Completions, temperature 0, reasoning off) answers from the Chunks it is given, numbered with their Contextual headers; inline [n] markers become Citations, numbers matching no Chunk are dropped and counted · newest dated mini snapshot (gpt-4.1-mini is deprecated, gpt-6 names have no dated snapshot); markers carry over to the chat UI; no retrieval inside, so the agent reuses it
- 2026-10-26 · Numeric check: a Question is numeric when FinanceBench's whole answer is one number; the Answer matches when any of its numbers (not markers, "10-K" or "FY2017"; a % also as its ratio) is within 1%, sizes only; no scale word or % in the gold → any power-of-1000 scale · Answers often give the sign in words ("fell 3.7%") and the unit only in the Question; lenient because it cross-checks the Judge (#36), not the headline metric
- 2026-10-27 · Judge: gpt-5.4-2026-03-05 grades correctness against FinanceBench's answer (correct / incorrect / refused) and faithfulness from only the Answer and the Chunks it cites (supported / not supported); strict JSON schema, reason first; no reply → unjudged, counted; reasons kept local · at least as capable as the Answer model at half gpt-5.5's price; refusal kept apart from incorrect; disagreement with the numeric check compares only correct/incorrect grades (docs/adr/0003). `dense-baseline` can't run on the headered corpus, so the first answer runs are `dense-headers` vs `keyword-bm25-headers`, the widest retrieval gap

## Open questions
- None

## Progress log
- 2026-10-14 · Repo bootstrapped; README (problem + planned approach). 2026-10-15 · Scope widened to any company via EDGAR; week-1 spec published as issue #2
- 2026-10-15 · uv skeleton, CI (lint + unit tests), ruff lint hook; push gate hook (no main, reviewed HEAD, no merged-PR branches); `env.example` rename (#4). Postgres + pgvector (Docker :5433), `make db-up` / `make db-reset`, documents + chunks schema (#5); tracer bullet: fixture PDF → pypdfium2 Pages → fake Embedder → Postgres → `Retriever.search`; GLOSSARY.md (#6)
- 2026-10-16 · Page-bounded chunking, 512 tokens with 64 overlap (cl100k_base); text-less PDFs refused (#7); retrieval scoring: `score()` → Hit@1/5/10, Recall@10, MRR@10 per Question, per type, overall (#8)
- 2026-10-16 · `make data`: FinanceBench Questions (Doc types normalized, e.g. 10k → 10-K) + 84 PDFs, pinned; `make split`: `eval/splits/financebench_v1.json`, 50 dev (17/17/16 by type) / 100 test, seed 2026 (#9)
- 2026-10-19 · Evidence pages aligned to 1-based Pages; local check on 20 sampled Questions vs FinanceBench's full-page text (#10). `OpenAIEmbedder` (text-embedding-3-small, batches of 256, injected client; fake client for tests); `make ingest`: cost prompt before any API call, resumable; 84 Documents, 25,854 Chunks, 10.5M tokens (≈ $0.21) stored; Doc type CHECK (#11)
- 2026-10-19 · `make eval`: dense-only baseline on dev, Hit@5 0.40 · MRR@10 0.24; 27 of 30 misses retrieve the right Document but the wrong Page (#12)
- 2026-10-20 · Week-2 spec #26 and tickets #27–#38
- 2026-10-21 · `make eval EXPERIMENT=` builds a named Experiment; runs record commit, Document/Chunk counts, Questions under 10 Pages; atomic UTF-8 writes (#27)
- 2026-10-22 · Corpus settings in the database; ingest refuses mixed settings; runs read them from the database; re-ingest #1 (#28, part 1). `keyword-bm25` on dev: Hit@5 0.10 · MRR@10 0.11 (dense 0.40 · 0.24); right company, wrong year or Page; only 2 Questions in the top 10 by keyword but not dense (#28)
- 2026-10-23 · `hybrid-rrf` on dev: Hit@5 0.26 · MRR@10 0.18; 4 Questions gained, 11 lost from dense's top 5; evidence in the 50 Chunks for 34 Questions (dense 39, re-run on the same corpus) (#29). `dense-rerank-50` / `-100` on dev: Hit@5 0.32 / 0.30 · MRR@10 0.21 / 0.20, ~10 / 15 s per Question; 5 / 4 gained, 9 / 9 lost vs dense; only ~1% of text cut at 512 tokens (10% sample of Chunks) (#30)
- 2026-10-24 · `dense-oracle-filter` on dev, an upper bound: Hit@5 0.60 · MRR@10 0.38 (dense 0.40 · 0.24); 10 Questions gained, 0 lost; 123 of dense's 250 top-5 Pages are from other Documents (#31)
- 2026-10-25 · Re-ingest #2 with Contextual headers (10.8M tokens, ≈ $0.22). Dev Hit@5 · MRR@10: `dense-headers` 0.54 · 0.31 (9 Questions gained, 2 lost vs dense), `hybrid-rrf-headers` 0.46 · 0.32 (best Hit@1, 0.24), `keyword-bm25-headers` 0.20 · 0.15; dense's top-5 Pages from other Documents 123 → 105 (#32)
- 2026-10-25 · `OpenAIAnswerer` (Question + Chunks → Answer with Citations) and `FakeAnswerer`; `make check-answer`: one numeric dev Question answered with FinanceBench's figure, citing its Evidence page, for under a cent (#33)
- 2026-10-26 · Answer scoring: `score_answers()` → citation hit rate (cites ≥ 1 Evidence page) and invalid citations, overall and per type; `run_answer_eval()`: top 10 Chunks per Question to the Answerer, runs in `eval/answer_runs/`, an answer table in RESULTS.md; `make answer-eval` asks about the cost ceiling first, dev ≤ $0.45 (#34)
- 2026-10-26 · `numeric_match()` and numeric-check accuracy (numeric Questions only) in answer scoring, answer runs and the answer table; 52 of 150 Questions numeric, 17 in dev, all of dev's metrics-generated (#35)
- 2026-10-27 · `OpenAIJudge` + `FakeJudge`; answer runs record verdicts, reasons stay in the `.local.jsonl`; first paid dev answer runs (ceiling $1.96 each). Accuracy · refused · faithful · citation hit: `dense-headers` 0.60 · 0.14 · 0.63 · 0.62, `keyword-bm25-headers` 0.30 · 0.40 · 0.47 · 0.22; numeric check 0.65 vs 0.12 of 17, Judge–numeric disagreement 0 in both; 7 correct `dense-headers` Answers add a claim their excerpts don't state (#36)

## How to resume
1. Read this file, `git log --oneline -20` and the open `ready-for-agent` issues. 2. Take the first unchecked task.
3. If it touches an open question, grill the user first; feature specs come from `/to-spec`. 4. Update this file in the same PR.
