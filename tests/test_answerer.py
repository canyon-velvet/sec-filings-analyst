from fakes.openai_client import FakeOpenAIClient

from sec_filings_analyst.answerer import OpenAIAnswerer
from sec_filings_analyst.documents import Chunk, Document

ACME = Document("ACME_2023_10K", "ACME", "10-K", 2023)
BETA = Document("BETA_2022_10Q", "Beta", "10-Q", 2022)
CHUNKS = [
    Chunk(ACME, 12, 0, "Revenue was 40 million dollars.", 6),
    Chunk(BETA, 3, 1, "Net income fell 5%.", 5),
    Chunk(ACME, 40, 0, "Capital expenditures were 7 million dollars.", 6),
]


def cited(answer) -> list[tuple[str, int]]:
    return [(c.chunk.document.name, c.chunk.page) for c in answer.citations]


def test_markers_become_citations_to_the_chunks_they_number_in_first_cited_order():
    reply = "Revenue was $40M [1] and capex $7M [3]; Beta's income fell [2, 3]."
    client = FakeOpenAIClient(reply)

    answer = OpenAIAnswerer(client).answer("What were ACME's revenue and capex?", CHUNKS)

    assert answer.text == reply
    assert cited(answer) == [("ACME_2023_10K", 12), ("ACME_2023_10K", 40), ("BETA_2022_10Q", 3)]
    assert [c.number for c in answer.citations] == [1, 3, 2]


def test_markers_matching_no_provided_chunk_are_dropped_from_the_text_and_counted():
    client = FakeOpenAIClient("Revenue was $40M [1, 4] [0]. Capex is not given [7].")

    answer = OpenAIAnswerer(client).answer("What were ACME's revenue and capex?", CHUNKS)

    assert answer.text == "Revenue was $40M [1]. Capex is not given."
    assert cited(answer) == [("ACME_2023_10K", 12)]
    assert answer.invalid_citations == 3


def test_asks_the_pinned_model_at_temperature_0_with_each_chunk_under_its_number():
    client = FakeOpenAIClient("Revenue was $40M [1].")

    OpenAIAnswerer(client).answer("What was ACME's revenue?", CHUNKS)

    (request,) = client.chat_requests
    assert request["model"] == "gpt-5.4-mini-2026-03-17"
    assert (request["temperature"], request["reasoning_effort"]) == (0, "none")
    assert request["max_completion_tokens"] == 1000  # so an answer run's cost has a ceiling
    prompt = request["messages"][-1]["content"]
    assert "What was ACME's revenue?" in prompt
    assert "[2] Beta 10-Q FY2022, page 3\nNet income fell 5%." in prompt


def test_a_reply_without_text_is_an_answer_citing_nothing():  # the SDK gives None on a refusal
    answer = OpenAIAnswerer(FakeOpenAIClient(reply=None)).answer("What was ACME's revenue?", CHUNKS)

    assert (answer.text, answer.citations, answer.invalid_citations) == ("", [], 0)
