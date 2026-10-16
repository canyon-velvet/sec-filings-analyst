from http.client import IncompleteRead
from pathlib import Path

import pytest
from fakes.fetcher import FakeFetcher

from sec_filings_analyst.documents import Document
from sec_filings_analyst.financebench import (
    PDF_URL,
    QUESTIONS_URL,
    Question,
    download,
    load_questions,
)

# Three invented rows in FinanceBench's shape: two Questions on 3M_2018_10K, one on an 8-K.
FIXTURE = Path(__file__).parent / "fixtures" / "financebench.jsonl"
MMM = Document(name="3M_2018_10K", company="3M", doc_type="10-K", fiscal_year=2018)
AMCOR = Document("AMCOR_2022_8K_dated-2022-07-01", "AMCOR", "8-K", 2022)


def test_loads_questions_with_their_document_and_evidence_pages():
    questions = load_questions(FIXTURE)

    assert questions[0] == Question(
        id="financebench_id_00001",
        question_type="metrics-generated",
        document=MMM,
        text="What was 3M's FY2018 capital expenditure?",
        answer="$1,577 million",
        evidence_pages=frozenset({59, 60}),
    )
    assert [q.document for q in questions] == [MMM, MMM, AMCOR]  # doc_type 10k → 10-K, 8k → 8-K


def fetcher_serving(pdfs):
    responses = {QUESTIONS_URL: FIXTURE.read_bytes()}
    responses |= {PDF_URL.format(name=name): content for name, content in pdfs.items()}
    return FakeFetcher(responses)


def test_downloads_the_questions_and_each_document_once(tmp_path):
    fetch = fetcher_serving({MMM.name: b"%PDF-1.4 3M", AMCOR.name: b"%PDF-1.4 Amcor"})

    download(tmp_path, fetch)

    assert len(load_questions(tmp_path / "financebench_merged.jsonl")) == 3
    assert (tmp_path / "pdfs" / "3M_2018_10K.pdf").read_bytes() == b"%PDF-1.4 3M"
    assert (tmp_path / "pdfs" / f"{AMCOR.name}.pdf").read_bytes() == b"%PDF-1.4 Amcor"
    assert len(fetch.urls) == 3  # the Questions file + 2 Documents, though 3M has two Questions


def test_skips_files_already_downloaded(tmp_path):
    download(tmp_path, fetcher_serving({MMM.name: b"%PDF-1.4 3M", AMCOR.name: b"%PDF-1.4 Amcor"}))
    (tmp_path / "pdfs" / f"{AMCOR.name}.pdf").unlink()
    fetch = fetcher_serving({AMCOR.name: b"%PDF-1.4 Amcor"})

    download(tmp_path, fetch)

    assert fetch.urls == [PDF_URL.format(name=AMCOR.name)]


@pytest.mark.parametrize(
    "amcor_pdfs",
    [
        {},
        {AMCOR.name: IncompleteRead(b"%PDF-1.4 Amc", expected=10)},
        {AMCOR.name: b"<html>Rate limit exceeded</html>"},
    ],
    ids=["fetch fails", "connection drops mid-download", "not a PDF"],
)
def test_a_failed_document_raises_naming_it_and_leaves_no_file(tmp_path, amcor_pdfs):
    fetch = fetcher_serving({MMM.name: b"%PDF-1.4 3M"} | amcor_pdfs)

    with pytest.raises(RuntimeError, match=AMCOR.name):
        download(tmp_path, fetch)

    assert not list((tmp_path / "pdfs").glob("AMCOR*"))
