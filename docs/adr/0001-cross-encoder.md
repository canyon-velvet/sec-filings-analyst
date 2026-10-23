# 1. Reranking cross-encoder: ms-marco-MiniLM-L6-v2 on ONNX Runtime

Date: 2026-10-23 · Status: accepted · Ticket: #30

## Context

Dense search compares the Question's embedding with each Chunk's, made separately, so it can't
weigh how the Question's words relate to the Chunk's. A cross-encoder reads the Question and a
Chunk's text together and scores the pair: more accurate, too slow for the whole corpus, so it
re-orders only the first stage's top candidates. Week 2 requires that it run locally on CPU (no
API cost), with a permissive license and a pinned revision.

The development machine is an Intel Mac. PyTorch publishes no macOS x86_64 wheels after 2.2, so
`sentence-transformers` (which needs torch) can't be installed there.

## Decision

- **Model:** `cross-encoder/ms-marco-MiniLM-L6-v2`, **Apache-2.0**, revision
  `233902d25c440f23af6f7d6e94d2946bac0bee0a`. 22.7M parameters, trained on MS MARCO passage
  ranking; inputs are cut at 512 of its own tokens.
- **Runtime:** its published ONNX export (`onnx/model.onnx`) with ONNX Runtime on CPU, and its
  `tokenizer.json` with Hugging Face `tokenizers`; both downloaded at the pinned revision into the
  Hugging Face cache on first use. `onnxruntime` is pinned to `>=1.23.2,<1.24`: the last series
  with macOS x86_64 wheels.
- **Isolation:** these libraries are in the `rerank` dependency group, which CI doesn't install;
  the Scorer imports them only when built, and a unit test checks that loading the Experiments
  doesn't.
- **Check:** in a one-off manual check (not a test: tests never load the model), the scorer
  reproduced the model card's example scores (8.607, −4.320).

## Alternatives

- `BAAI/bge-reranker-base` (MIT, 278M, mostly its vocabulary): stronger on general benchmarks,
  but 12 layers × 768 wide against 6 × 384, about 8× the compute per token: roughly 1.5 minutes
  per Question for 100 Chunks on this CPU.
- `sentence-transformers` `CrossEncoder`: the usual API, but needs torch (see Context).
- An LLM as reranker (API): no local model, but costs money per run and isn't a cross-encoder.

## Consequences

- Cost on this machine (12 cores), wall time: a benchmark of 100 full-length pairs alone took
  10.8 s; the dev runs took 524 s (50 candidates) and 772 s (100) for 50 Questions, about 10 and
  15 s per Question including the dense search. The week-3 agent pays that per search unless it
  reranks fewer.
- MS MARCO is web search, not financial filings: tables and figures may score poorly.
- Moving to an ARM machine or a newer onnxruntime means revisiting the pin, not the code.
