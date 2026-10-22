import hashlib
import re

DIMENSIONS = 1536


class WordHashEmbedder:
    """Deterministic, offline Embedder: each word adds 1 to the dimension its hash picks,
    so texts that share words are similar."""

    model = "word-hash"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for word in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(word.encode()).digest()
            vector[int.from_bytes(digest[:4]) % DIMENSIONS] += 1.0
        return vector
