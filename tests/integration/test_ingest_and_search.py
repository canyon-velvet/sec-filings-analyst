from pathlib import Path

import pypdfium2
import pytest
from fakes.embedder import WordHashEmbedder
from fakes.openai_client import FakeOpenAIClient

from sec_filings_analyst.documents import Document
from sec_filings_analyst.embedder import OpenAIEmbedder
from sec_filings_analyst.ingest import describe_corpus, ingest
from sec_filings_analyst.retriever import Filter, KeywordSearcher, Retriever

pytestmark = pytest.mark.integration

# Page 1: revenue · Page 2: empty · Page 3: debt
FIXTURE = Path(__file__).parents[1] / "fixtures" / "sample.pdf"
ACME = Document(name="ACME_2023_10K", company="ACME", doc_type="10-K", fiscal_year=2023)


class ScriptedConfirm:
    """A confirm() for ingest: records each cost summary it's asked about and answers yes or no."""

    def __init__(self, yes: bool):
        self.yes = yes
        self.summaries: list[str] = []

    def __call__(self, summary: str) -> bool:
        self.summaries.append(summary)
        return self.yes


def test_search_ranks_the_page_that_matches_the_query_first(db):
    ingest({ACME: FIXTURE}, WordHashEmbedder(), db, ScriptedConfirm(yes=True))

    results = Retriever(db, WordHashEmbedder()).search("How much long-term debt was reduced?", k=5)

    assert [(r.chunk.document, r.chunk.page) for r in results] == [(ACME, 3), (ACME, 1)]
    assert results[0].chunk.text == "Long-term debt was reduced by 300 million dollars."


def test_chunks_are_embedded_and_keyword_indexed_with_their_header_but_stored_without(db):
    client = FakeOpenAIClient()

    ingest({ACME: FIXTURE}, OpenAIEmbedder(client), db, ScriptedConfirm(yes=True))

    (request,) = client.requests
    debt = "Long-term debt was reduced by 300 million dollars."
    assert request["input"][1] == f"ACME 10-K FY2023, page 3\n{debt}"
    results = KeywordSearcher(db).search("ACME", k=5)  # the name is only in the headers
    assert sorted(r.chunk.page for r in results) == [1, 3]
    assert [r.chunk.text for r in results if r.chunk.page == 3] == [debt]


def test_keyword_search_finds_a_page_by_any_of_the_question_s_terms(db):
    ingest({ACME: FIXTURE}, WordHashEmbedder(), db, ScriptedConfirm(yes=True))

    # "unicorn" is on no Page, so requiring every term would find nothing
    question = "What was the long-term debt reduction in the unicorn division?"
    results = KeywordSearcher(db).search(question, k=5)

    assert [(r.chunk.document, r.chunk.page) for r in results] == [(ACME, 3)]  # Page 1: no term


SEARCHERS = {
    "dense": lambda db: Retriever(db, WordHashEmbedder()),
    "keyword": KeywordSearcher,
}


@pytest.mark.parametrize("searcher", SEARCHERS.values(), ids=SEARCHERS.keys())
def test_a_filter_keeps_only_the_chunks_of_matching_documents(db, searcher):
    # Each other Document differs from ACME's 2023 10-K in one field
    others = [
        Document(name="BETA_2023_10K", company="Beta", doc_type="10-K", fiscal_year=2023),
        Document(name="ACME_2022_10K", company="ACME", doc_type="10-K", fiscal_year=2022),
        Document(name="ACME_2023_Q3_10Q", company="ACME", doc_type="10-Q", fiscal_year=2023),
    ]
    # Same text in all four, and ACME's Chunks are stored last, so they lose every tie: k=2 only
    # reaches them if the filter applies before the top-k cut
    documents = {document: FIXTURE for document in [*others, ACME]}
    ingest(documents, WordHashEmbedder(), db, ScriptedConfirm(yes=True))
    acme_10k_2023 = Filter(company="ACME", doc_type="10-K", fiscal_year=2023)

    results = searcher(db).search("revenue and long-term debt", k=2, filter=acme_10k_2023)

    assert sorted((r.chunk.document, r.chunk.page) for r in results) == [(ACME, 1), (ACME, 3)]


def test_the_corpus_is_described_by_its_counts_and_how_its_chunks_were_made(db):
    ingest({ACME: FIXTURE}, WordHashEmbedder(), db, ScriptedConfirm(yes=True))

    assert describe_corpus(db) == {
        "documents": 1,
        "chunks": 2,  # Page 2 is empty
        "embedding_model": "word-hash",  # the fake's: read back from the database
        "chunk_tokens": 512,
        "overlap_tokens": 64,
        "header_format": "{company} {doc_type} FY{fiscal_year}, page {page}",
    }


def test_a_corpus_without_settings_points_to_db_reset_and_ingest(db):
    with pytest.raises(RuntimeError, match="make db-reset.*make ingest"):
        describe_corpus(db)  # nothing ingested yet

    db.execute("ALTER TABLE corpus_settings DROP COLUMN header_format")  # from before headers
    with pytest.raises(RuntimeError, match="make db-reset.*make ingest"):
        describe_corpus(db)

    db.execute("DROP TABLE corpus_settings")  # a schema from before corpus settings
    with pytest.raises(RuntimeError, match="make db-reset.*make ingest"):
        describe_corpus(db)


def test_ingest_refuses_a_connection_that_might_not_commit(db):
    db.autocommit = False

    with pytest.raises(ValueError, match="autocommit"):
        ingest({ACME: FIXTURE}, WordHashEmbedder(), db, ScriptedConfirm(yes=True))


def test_ingest_refuses_a_pdf_without_text_and_stores_nothing(db, tmp_path):
    scanned = tmp_path / "scanned.pdf"  # one blank Page, like a scan with no text layer
    with pypdfium2.PdfDocument.new() as blank:
        blank.new_page(612, 792)
        blank.save(scanned)

    with pytest.raises(ValueError, match="ACME_2023_10K"):
        ingest({ACME: scanned}, WordHashEmbedder(), db, ScriptedConfirm(yes=True))

    assert Retriever(db, WordHashEmbedder()).search("anything", k=5) == []


def test_declining_the_cost_embeds_and_stores_nothing(db):
    client, confirm = FakeOpenAIClient(), ScriptedConfirm(yes=False)

    ingest({ACME: FIXTURE}, OpenAIEmbedder(client), db, confirm)

    # Page 1: 20 tokens, Page 3: 11, plus 13 for each header line (cl100k_base): the 512-token
    # limit is on the Page text, and the header is paid for on top; $0.02 per million tokens
    assert confirm.summaries == ["Documents: 1, Chunks: 2, tokens: 57, estimated cost: $0.0000"]
    assert client.requests == []
    assert Retriever(db, WordHashEmbedder()).search("anything", k=5) == []


def test_confirming_stores_every_document_and_a_rerun_skips_stored_ones(db):
    beta = Document(name="BETA_2023_10K", company="Beta", doc_type="10-K", fiscal_year=2023)
    client = FakeOpenAIClient()
    ingest({ACME: FIXTURE}, OpenAIEmbedder(client), db, ScriptedConfirm(yes=True))
    rerun = ScriptedConfirm(yes=True)

    ingest({ACME: FIXTURE, beta: FIXTURE}, OpenAIEmbedder(client), db, rerun)  # like a resumed run

    # Beta's header lines are 12 tokens each, one fewer than ACME's
    assert rerun.summaries == ["Documents: 1, Chunks: 2, tokens: 55, estimated cost: $0.0000"]
    assert [len(r["input"]) for r in client.requests] == [2, 2]  # ACME once, then Beta
    results = Retriever(db, WordHashEmbedder()).search("long-term debt", k=10)
    assert sorted((r.chunk.document.name, r.chunk.page) for r in results) == [
        ("ACME_2023_10K", 1),
        ("ACME_2023_10K", 3),
        ("BETA_2023_10K", 1),
        ("BETA_2023_10K", 3),
    ]


def test_ingest_refuses_to_mix_chunks_made_with_other_settings(db):
    beta = Document(name="BETA_2023_10K", company="Beta", doc_type="10-K", fiscal_year=2023)
    ingest({ACME: FIXTURE}, WordHashEmbedder(), db, ScriptedConfirm(yes=True))
    client, confirm = FakeOpenAIClient(), ScriptedConfirm(yes=True)

    # Like resuming after switching the embedding model: Beta would be embedded differently
    with pytest.raises(RuntimeError, match="word-hash.*text-embedding-3-small.*make db-reset"):
        ingest({beta: FIXTURE}, OpenAIEmbedder(client), db, confirm)

    assert confirm.summaries == [] and client.requests == []  # refused before any cost
    assert describe_corpus(db)["documents"] == 1


def test_a_missing_or_outdated_schema_points_to_make_db_reset(db):
    db.execute("ALTER TABLE corpus_settings DROP COLUMN header_format")  # from before headers
    with pytest.raises(RuntimeError, match="make db-reset"):
        ingest({ACME: FIXTURE}, WordHashEmbedder(), db, ScriptedConfirm(yes=True))

    db.execute("DROP TABLE chunks, documents")
    with pytest.raises(RuntimeError, match="make db-reset"):
        ingest({ACME: FIXTURE}, WordHashEmbedder(), db, ScriptedConfirm(yes=True))
