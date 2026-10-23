from sec_filings_analyst.documents import Chunk, Document
from sec_filings_analyst.retriever import SearchResult


class FakeRetriever:
    """Offline Retriever: answers each query with canned (Document name, Page) hits, best first,
    one Chunk per hit (text "<name> page <page>"), and records every k it was asked for."""

    def __init__(self, hits: dict[str, list[tuple[str, int]]]):
        self._hits = hits
        self.ks: list[int] = []

    def search(self, query: str, k: int) -> list[SearchResult]:
        self.ks.append(k)
        return [
            SearchResult(
                Chunk(Document(name, "Co", "10-K", 2020), page, 0, f"{name} page {page}", 1),
                score=1.0,
            )
            for name, page in self._hits[query][:k]
        ]
