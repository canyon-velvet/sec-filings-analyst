from types import SimpleNamespace

from fakes.embedder import WordHashEmbedder


class FakeOpenAIClient:
    """Offline stand-in for openai.OpenAI's embeddings endpoint: records each request and
    answers with WordHashEmbedder's vectors, in input order."""

    def __init__(self):
        self.embeddings = self  # so client.embeddings.create(...) works like the SDK
        self.requests: list[dict] = []  # each: {"model": ..., "input": [...]}

    def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
        self.requests.append({"model": model, "input": input})
        vectors = WordHashEmbedder().embed(input)
        return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])
