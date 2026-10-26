"""Answerer: a Question and the Chunks found for it become an Answer that cites them. It does no
retrieval, so evaluation and the agent can each pass whatever Chunks they found."""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from sec_filings_analyst.chunking import contextual_header
from sec_filings_analyst.documents import Chunk

if TYPE_CHECKING:  # the SDK is heavy; only OpenAIAnswerer's caller needs it loaded
    import openai

ANSWER_MODEL = "gpt-5.4-mini-2026-03-17"  # pinned dated snapshot
INSTRUCTIONS = (
    "Answer the question about a company's financial documents using only the numbered excerpts."
    " Cite each claim with the number of the excerpt it comes from in square brackets, e.g. [1]"
    " or [2][3]. If the excerpts don't contain the answer, say you can't find it in the"
    " documents; never guess a number."
)
# One or more excerpt numbers in brackets, with the whitespace before it: " [3]", " [2, 3]"
_MARKER = re.compile(r"(\s*)\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True)
class Citation:
    number: int  # the marker in the Answer's text, e.g. 3 for [3]
    chunk: Chunk  # so (Document, Page)


@dataclass(frozen=True)
class Answer:
    text: str  # with inline markers, e.g. "Capex was $1,577M [2]."
    citations: list[Citation]  # one per cited Chunk, in the order first cited
    invalid_citations: int  # marker numbers matching no provided Chunk, dropped from the text


class Answerer(Protocol):
    model: str  # recorded with answer runs

    def answer(self, question: str, chunks: list[Chunk]) -> Answer: ...


class OpenAIAnswerer:
    """Answers with ANSWER_MODEL from Chunks numbered [1], [2], … in the prompt."""

    model = ANSWER_MODEL

    def __init__(self, client: "openai.OpenAI"):
        self._client = client

    def answer(self, question: str, chunks: list[Chunk]) -> Answer:
        excerpts = "\n\n".join(
            f"[{n}] {contextual_header(chunk)}\n{chunk.text}" for n, chunk in enumerate(chunks, 1)
        )
        response = self._client.chat.completions.create(
            model=ANSWER_MODEL,
            temperature=0,  # the snapshot takes a temperature only without reasoning
            reasoning_effort="none",
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {"role": "user", "content": f"Question: {question}\n\nExcerpts:\n\n{excerpts}"},
            ],
        )
        return cite(response.choices[0].message.content, chunks)


def cite(text: str, chunks: list[Chunk]) -> Answer:
    """The Answer a reply makes: marker n cites chunks[n - 1]; numbers matching no Chunk are
    dropped from the text and counted."""
    cited: list[int] = []
    invalid = 0

    def keep_valid(marker: re.Match) -> str:
        nonlocal invalid
        numbers = [int(n) for n in marker[2].split(",")]
        valid = [n for n in numbers if 1 <= n <= len(chunks)]
        invalid += len(numbers) - len(valid)
        for n in valid:
            if n not in cited:
                cited.append(n)
        # a marker left with no valid number goes, with the space before it
        return f"{marker[1]}[{', '.join(map(str, valid))}]" if valid else ""

    text = _MARKER.sub(keep_valid, text)
    return Answer(text, [Citation(n, chunks[n - 1]) for n in cited], invalid)
