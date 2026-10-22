"""BM25 ranking over term counts: rare terms weigh more than common ones (IDF), and repeating a
term helps less and less (term-frequency saturation)."""

import math

K1 = 1.2  # term-frequency saturation
B = 0.75  # how much longer Chunks are penalized


class Bm25:
    def __init__(self, postings: dict[str, dict[int, int]]):
        """postings: term → {Chunk id: how often the term appears in it}; a Chunk's length is
        the sum of its counts."""
        self._postings = postings
        lengths: dict[int, int] = {}
        for counts in postings.values():
            for chunk, tf in counts.items():
                lengths[chunk] = lengths.get(chunk, 0) + tf
        self._n = len(lengths)
        average = sum(lengths.values()) / self._n if self._n else 0
        self._norm = {chunk: K1 * (1 - B + B * n / average) for chunk, n in lengths.items()}

    def top(self, terms: list[str], k: int) -> list[tuple[int, float]]:
        """The k Chunks sharing any term, highest score first (ties: lower id first); repeated
        terms count once."""
        scores: dict[int, float] = {}
        for term in set(terms):
            counts = self._postings.get(term, {})
            idf = math.log(1 + (self._n - len(counts) + 0.5) / (len(counts) + 0.5))
            for chunk, tf in counts.items():
                score = idf * tf * (K1 + 1) / (tf + self._norm[chunk])
                scores[chunk] = scores.get(chunk, 0.0) + score
        return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]
