# SEC Filings Analyst

Ask questions about the SEC filings of 32 public companies (the [FinanceBench](https://arxiv.org/abs/2311.11944) set) in plain English and get answers that cite the exact document and page.

## The problem

Answering a simple financial question ("How did Amazon's operating margin change from 2021 to 2022?", "Compare Adobe's and Activision's R&D intensity") means digging through 100+ page 10-Ks and 10-Qs, finding the right table, checking the fiscal year and doing the math yourself.

LLMs don't solve this out of the box:

- **From memory**, they make up numbers and can't cite a source.
- **With basic retrieval** ("chat with your PDF"), they still struggle. Financial documents are dense with tables, nearly identical from year to year, and questions often span several companies. The FinanceBench paper reports that "GPT-4-Turbo used with a retrieval system incorrectly answered or refused to answer 81% of questions."

In finance, an answer you can't verify isn't useful.

## The planned approach

- **Agentic retrieval:** an agent will search each company and period separately, compute ratios, then answer, citing every figure to a document and page.
- **Measured, not assumed:** each retrieval technique (hybrid search, reranking, metadata filters) will be evaluated on FinanceBench with a held-out test split, and its gain reported in a results table.
- **Chat UI:** multi-turn conversations with clickable citations and a visible trace of the agent's steps.

🚧 Work in progress. See [SPEC.md](SPEC.md) for the roadmap, stack and decisions.

## License

[MIT](LICENSE). FinanceBench data is CC-BY-NC-4.0 and is not redistributed here.
