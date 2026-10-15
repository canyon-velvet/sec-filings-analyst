# SPEC: SEC Filings Analyst
Chat with an agent about FinanceBench companies' SEC filings; answers cite doc + page.
Quality is proven by evals. Portfolio project for AI-engineer roles.

## Scope
- In: FinanceBench companies only · multi-turn chat · multi-company comparisons via agent tools · cited answers · eval harness + ablations
- Out (for now): adding arbitrary companies (EDGAR) · auth · nightly CI

## Stack
Python 3.12 + uv · FastAPI (SSE) · Postgres + pgvector (Docker, :5433) + Postgres FTS · pypdfium2 ·
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
- [ ] Python skeleton + ruff lint hook + pre-push review gate
- [ ] Postgres + pgvector via Docker; schema
- [ ] Download FinanceBench + PDFs; dev/test split
- [ ] Ingest: parse per page → page-bounded chunks (512/64 tok) → embed → store
- [ ] Retrieval metrics (TDD) + dense-only baseline on dev
### Week 2: hybrid (RRF) · reranker · metadata filters · contextual headers · cited answers + answer evals
### Week 3: agent tools + loop · follow-ups · /chat SSE · chat UI · agent evals
### Week 4: CI eval smoke · cost/latency · deploy · README

## Decisions (date · decision · why)
- 2026-10-14 · FinanceBench companies only · every answerable question is measurable
- 2026-10-14 · Hand-rolled agent tool loop · multi-company comparisons; shows fundamentals
- 2026-10-14 · pgvector in Docker on :5433 · reproducible; local PG14 lacks pgvector
- 2026-10-14 · Page-bounded chunks · each chunk maps to one page → clean citations and metrics
- 2026-10-14 · Dev/test split · avoids overfitting the reported numbers
- 2026-10-14 · No nightly CI · nothing changes without a commit; model snapshots pinned
- 2026-10-14 · PRs ≤ ~200 lines + 3 reviews before push · easy review
- 2026-10-14 · pypdfium2 + MIT license · permissive end to end (pymupdf is AGPL)
- 2026-10-14 · Python at repo root · one project; simple commands, CI and hooks
- 2026-10-14 · Exact search, no ANN index in week 1 · keeps approximation noise out of the baseline

## Open questions
- Verify during implementation: FinanceBench page numbers 0- or 1-based (test against evidence_text_full_page) ·
  PDFs present in FinanceBench's GitHub repo

## Progress log
- 2026-10-14 · Repo bootstrapped

## How to resume
1. Read this file, `git log --oneline -20` and the open `ready-for-agent` issues. 2. Take the first unchecked task.
3. If it touches an open question, grill the user first; feature specs come from `/to-spec`. 4. Update this file in the same PR.
