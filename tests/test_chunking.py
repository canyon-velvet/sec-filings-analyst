from pathlib import Path

from fakes.tokenizer import WordTokenizer

from sec_filings_analyst.chunking import chunk_pdf
from sec_filings_analyst.documents import Document

# Page 1: the 1000 words w0 … w999 · Page 2: empty · Page 3: "A short page of text."
FIXTURE = Path(__file__).parent / "fixtures" / "chunking.pdf"
ACME = Document(name="ACME_2023_10K", company="ACME", doc_type="10-K", fiscal_year=2023)


def summarize(chunk):
    words = chunk.text.split()
    return chunk.page, chunk.position, chunk.token_count, words[0], words[-1]


def test_long_page_splits_into_512_token_chunks_overlapping_by_64():
    chunks = chunk_pdf(FIXTURE, ACME, WordTokenizer())

    # Windows start every 512 - 64 = 448 tokens: w0-w511, w448-w959, w896-w999.
    assert [summarize(c) for c in chunks if c.page == 1] == [
        (1, 0, 512, "w0", "w511"),
        (1, 1, 512, "w448", "w959"),
        (1, 2, 104, "w896", "w999"),
    ]


def test_short_page_gives_one_chunk_and_empty_page_gives_none():
    chunks = chunk_pdf(FIXTURE, ACME, WordTokenizer())

    assert [c.page for c in chunks] == [1, 1, 1, 3]
    assert summarize(chunks[-1]) == (3, 0, 5, "A", "text.")


def test_every_chunk_carries_its_document():
    chunks = chunk_pdf(FIXTURE, ACME, WordTokenizer())

    assert {c.document for c in chunks} == {ACME}
