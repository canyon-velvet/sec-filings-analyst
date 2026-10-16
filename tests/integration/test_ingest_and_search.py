from pathlib import Path

import pypdfium2
import pytest
from fakes.embedder import WordHashEmbedder

from sec_filings_analyst.documents import Document
from sec_filings_analyst.ingest import ingest
from sec_filings_analyst.retriever import Retriever

pytestmark = pytest.mark.integration

# Page 1: revenue · Page 2: empty · Page 3: debt
FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample.pdf"
ACME = Document(name="ACME_2023_10K", company="ACME", doc_type="10-K", fiscal_year=2023)


def test_search_ranks_the_page_that_matches_the_query_first(db):
    ingest(FIXTURE, ACME, WordHashEmbedder(), db)

    results = Retriever(db, WordHashEmbedder()).search("How much long-term debt was reduced?", k=5)

    assert [(r.chunk.document, r.chunk.page) for r in results] == [(ACME, 3), (ACME, 1)]
    assert results[0].chunk.text == "Long-term debt was reduced by 300 million dollars."


def test_ingest_refuses_a_connection_that_might_not_commit(db):
    db.autocommit = False

    with pytest.raises(ValueError, match="autocommit"):
        ingest(FIXTURE, ACME, WordHashEmbedder(), db)


def test_ingest_refuses_a_pdf_without_text_and_stores_nothing(db, tmp_path):
    scanned = tmp_path / "scanned.pdf"  # one blank Page, like a scan with no text layer
    blank = pypdfium2.PdfDocument.new()
    blank.new_page(612, 792)
    blank.save(scanned)

    with pytest.raises(ValueError, match="ACME_2023_10K"):
        ingest(scanned, ACME, WordHashEmbedder(), db)

    assert Retriever(db, WordHashEmbedder()).search("anything", k=5) == []
