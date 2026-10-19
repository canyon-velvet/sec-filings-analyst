from fakes.embedder import WordHashEmbedder
from fakes.openai_client import FakeOpenAIClient

from sec_filings_analyst.embedder import OpenAIEmbedder


def test_embeds_in_batches_of_256_with_vectors_in_input_order():
    client = FakeOpenAIClient()
    texts = [f"chunk {i} of {i + 1000}" for i in range(600)]
    expected = WordHashEmbedder().embed(texts)
    assert len({tuple(v) for v in expected}) == 600  # every vector unique, so order shows

    vectors = OpenAIEmbedder(client).embed(texts)

    assert [len(r["input"]) for r in client.requests] == [256, 256, 88]
    assert {r["model"] for r in client.requests} == {"text-embedding-3-small"}
    assert vectors == expected


def test_sends_no_request_for_no_texts():  # OpenAI rejects an empty input
    client = FakeOpenAIClient()

    assert OpenAIEmbedder(client).embed([]) == []
    assert client.requests == []
