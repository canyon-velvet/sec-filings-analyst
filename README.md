# SEC Filings Analyst

🚧 Work in progress. See [SPEC.md](SPEC.md) for the roadmap, stack and decisions.

Goal: ask questions about any public company's SEC filings in plain English and get answers that cite the exact document and location. Quality is measured on the [FinanceBench](https://arxiv.org/abs/2311.11944) open sample (32 companies, 150 questions with labeled evidence).

## The problem

Answering a simple financial question ("How did Amazon's operating margin change from FY2017 to FY2019?", "Compare Coca-Cola's and PepsiCo's operating margins in FY2022") means digging through 100+ page 10-Ks and 10-Qs, finding the right table, checking the fiscal year and doing the math yourself.

LLMs don't solve this out of the box:

- **From memory**, they make up numbers and can't cite a source.
- **With basic retrieval**, they still struggle. Financial documents are dense with tables, nearly identical from year to year, and questions often span several companies.

On the FinanceBench benchmark, the paper reports that "GPT-4-Turbo used with a retrieval system incorrectly answered or refused to answer 81% of questions."

In finance, an answer you can't verify isn't useful.

## The planned approach

- **Agentic retrieval:** an agent will search each company and period separately, compute ratios, then answer, citing every figure to its source document and location.
- **Measured, not assumed:** each retrieval technique (hybrid search, reranking, metadata filters) will be evaluated on FinanceBench with a held-out test split, and its gain reported in a results table.
- **Any filing:** name a ticker, form and year in the chat; the filing is fetched from SEC EDGAR and indexed on demand.
- **Chat UI:** multi-turn conversations with clickable citations and a visible trace of the agent's steps.

## License

[MIT](LICENSE). FinanceBench data is CC-BY-NC-4.0; its PDFs are not committed to this repo.
