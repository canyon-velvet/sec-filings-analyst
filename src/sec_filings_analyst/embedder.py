"""Embedder: turns a batch of texts into vectors. Knows nothing about where the texts came from."""

from typing import Protocol

import openai

EMBEDDING_MODEL = "text-embedding-3-small"  # pinned: 1536 dims, tokenized with cl100k_base
# OpenAI caps a request at 300k tokens; 256 Chunks of ≤ 512 tokens stay under 132k.
BATCH_SIZE = 256


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per text, in order; 1536 dimensions to match the `chunks` table."""
        ...


def to_pgvector(vector: list[float]) -> str:
    """The text form pgvector accepts, e.g. '[1.0,0.0]'."""
    return "[" + ",".join(map(str, vector)) + "]"


class OpenAIEmbedder:
    """Embeds with OpenAI, BATCH_SIZE texts per request; no request for no texts."""

    def __init__(self, client: openai.OpenAI):
        self._client = client

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            response = self._client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
            vectors.extend(item.embedding for item in response.data)
        return vectors
