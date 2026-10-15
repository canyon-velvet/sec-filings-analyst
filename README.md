# SEC Filings Analyst

Ask questions about public companies' SEC filings in plain English and get answers that cite the exact document and page.

## The problem

Answering a simple financial question ("How did Amazon's operating margin change from 2021 to 2022?", "Compare Adobe's and Activision's R&D intensity") means digging through 100+ page 10-Ks and 10-Qs, finding the right table, checking the fiscal year and doing the math yourself.

LLMs don't solve this out of the box:

- **From memory**, they make up numbers and can't cite a source.
- **With basic retrieval** ("chat with your PDF"), they still struggle. Financial documents are dense with tables, nearly identical from year to year, and questions often span several companies. On the [FinanceBench](https://arxiv.org/abs/2311.11944) benchmark, *GPT-4-Turbo with a retrieval system answered incorrectly or refused 81% of questions.*

In finance, an answer you can't verify isn't useful.

## The approach

- **Agentic retrieval:** an agent searches each company and period separately, computes ratios, then answers, citing every figure to a document and page.
- **Measured, not assumed:** every retrieval technique (hybrid search, reranking, metadata filters, ...) is evaluated on FinanceBench with a held-out test split, and its gain is reported in a results table.
- **Chat UI:** multi-turn conversations with clickable citations and a visible trace of the agent's steps.

## Status

🚧 Week 1 of 4: ingestion and a baseline retrieval evaluation. See [SPEC.md](SPEC.md) for the roadmap and decisions.

**Stack:** Python · FastAPI · Postgres + pgvector · OpenAI · React + TypeScript

## License

[MIT](LICENSE). FinanceBench data is CC-BY-NC-4.0 and is not redistributed here.
