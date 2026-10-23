class FakeScorer:
    """Offline cross-encoder: scores each (query, Chunk text) pair from a canned text → score map
    (0 for any other text), and records every batch of pairs it was given."""

    def __init__(self, scores: dict[str, float]):
        self._scores = scores
        self.calls: list[list[tuple[str, str]]] = []

    def score(self, pairs: list[tuple[str, str]]) -> list[float]:
        self.calls.append(pairs)
        return [self._scores.get(text, 0.0) for _, text in pairs]
