from types import SimpleNamespace

from fakes.embedder import WordHashEmbedder


class FakeOpenAIClient:
    """Offline stand-in for openai.OpenAI's embeddings and chat completions endpoints: records each
    request, answers embeddings with WordHashEmbedder's vectors (in input order) and every chat
    completion with the canned reply."""

    def __init__(self, reply: str = ""):
        self.embeddings = self  # so client.embeddings.create(...) works like the SDK
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._complete))
        self.requests: list[dict] = []  # each: {"model": ..., "input": [...]}
        self.chat_requests: list[dict] = []  # each: the keyword arguments sent
        self._reply = reply

    def create(self, *, model: str, input: list[str]) -> SimpleNamespace:
        self.requests.append({"model": model, "input": input})
        vectors = WordHashEmbedder().embed(input)
        return SimpleNamespace(data=[SimpleNamespace(embedding=v) for v in vectors])

    def _complete(self, **request) -> SimpleNamespace:
        self.chat_requests.append(request)
        message = SimpleNamespace(content=self._reply)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])
