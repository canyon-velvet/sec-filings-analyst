from pathlib import Path

import pytest
from fakes.embedder import WordHashEmbedder

from sec_filings_analyst.ingest import Document, ingest
from sec_filings_analyst.retriever import Retriever

pytestmark = pytest.mark.integration

# Page 1: revenue · Page 2: empty · Page 3: debt
FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample.pdf"
ACME = Document(name="ACME_2023_10K", company="ACME", doc_type="10-K", fiscal_year=2023)


def test_search_ranks_the_page_that_matches_the_query_first(db):
    ingest(FIXTURE, ACME, WordHashEmbedder(), db)

    results = Retriever(db, WordHashEmbedder()).search("How much long-term debt was reduced?", k=5)

    assert [(r.document, r.page) for r in results] == [(ACME, 3), (ACME, 1)]
    assert results[0].text == "Long-term debt was reduced by 300 million dollars."
