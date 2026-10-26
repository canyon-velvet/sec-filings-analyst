from sec_filings_analyst.answerer import Answer, cite
from sec_filings_analyst.documents import Chunk


class FakeAnswerer:
    """Offline Answerer: replies to each question with its canned text, whose markers cite the
    Chunks it is given as the real Answerer's would ([1] is the first), and records every
    (question, Chunks) it was asked."""

    model = "fake-answerer"

    def __init__(self, replies: dict[str, str]):
        self._replies = replies
        self.calls: list[tuple[str, list[Chunk]]] = []

    def answer(self, question: str, chunks: list[Chunk]) -> Answer:
        self.calls.append((question, chunks))
        return cite(self._replies[question], chunks)
