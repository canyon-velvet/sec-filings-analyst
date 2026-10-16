"""Embedder: turns a batch of texts into vectors. Knows nothing about where the texts came from."""

from typing import Protocol


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per text, in order; 1536 dimensions to match the `chunks` table."""
        ...


def to_pgvector(vector: list[float]) -> str:
    """The text form pgvector accepts, e.g. '[1.0,0.0]'."""
    return "[" + ",".join(map(str, vector)) + "]"
