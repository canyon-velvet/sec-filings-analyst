"""Judge: an LLM grades an Answer's correctness against FinanceBench's answer, and its
faithfulness to the Chunks it cites (and nothing else)."""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from sec_filings_analyst.answerer import Answer, excerpt

if TYPE_CHECKING:  # the SDK is heavy; only OpenAIJudge's caller needs it loaded
    import openai

JUDGE_MODEL = "gpt-5.4-2026-03-05"  # pinned dated snapshot, the Answer model's full-size sibling
INPUT_PRICE_PER_MILLION, OUTPUT_PRICE_PER_MILLION = 2.50, 15.00  # USD, JUDGE_MODEL's list prices
MAX_JUDGE_TOKENS = 300  # output cap per verdict, so a run's cost has a ceiling
CORRECTNESS = ["correct", "incorrect", "refused"]
FAITHFULNESS = ["supported", "not supported"]
UNJUDGED = "unjudged"  # the reply held no verdict (cut off, or refused): counted, not a crash
CORRECTNESS_INSTRUCTIONS = (
    "Grade an answer to a question about a company's financial documents against the reference"
    " answer. correct: it gives the reference's figure or conclusion; rounding and other units"
    " are fine (e.g. $2.4 billion for $2,400 million). incorrect: it gives a different figure or"
    " conclusion, or doesn't answer what was asked. refused: it says it can't find the answer and"
    " gives none. Give a one-sentence reason, then the verdict."
)
FAITHFULNESS_INSTRUCTIONS = (
    "Check whether an answer is supported by the numbered excerpts it cites. supported: every"
    " claim, figure and calculation in it follows from those excerpts. not supported: any of them"
    " is missing from the excerpts or doesn't follow from them. Use only the excerpts, not your"
    " own knowledge. Give a one-sentence reason, then the verdict."
)


@dataclass(frozen=True)
class Verdict:
    label: str  # one of CORRECTNESS or FAITHFULNESS, or UNJUDGED
    reason: str  # one sentence; can restate FinanceBench's answer, so it is never committed


class Judge(Protocol):
    model: str  # recorded with answer runs

    def correctness(self, question: str, expected: str, answer: str) -> Verdict: ...

    def faithfulness(self, answer: Answer) -> Verdict: ...


class OpenAIJudge:
    """Grades with JUDGE_MODEL, replying in a JSON schema that allows only the verdict labels."""

    model = JUDGE_MODEL

    def __init__(self, client: "openai.OpenAI"):
        self._client = client

    def correctness(self, question: str, expected: str, answer: str) -> Verdict:
        prompt = f"Question: {question}\n\nReference answer: {expected}\n\nAnswer: {answer}"
        return self._verdict(CORRECTNESS_INSTRUCTIONS, prompt, CORRECTNESS)

    def faithfulness(self, answer: Answer) -> Verdict:
        excerpts = "\n\n".join(excerpt(c.number, c.chunk) for c in answer.citations)
        prompt = f"Answer: {answer.text}\n\nCited excerpts:\n\n{excerpts}"
        return self._verdict(FAITHFULNESS_INSTRUCTIONS, prompt, FAITHFULNESS)

    def _verdict(self, instructions: str, prompt: str, labels: list[str]) -> Verdict:
        schema = {
            "type": "object",
            # the reason first, so the verdict follows from it
            "properties": {
                "reason": {"type": "string"},
                "verdict": {"type": "string", "enum": labels},
            },
            "required": ["reason", "verdict"],
            "additionalProperties": False,
        }
        response = self._client.chat.completions.create(
            model=JUDGE_MODEL,
            temperature=0,
            reasoning_effort="none",
            max_completion_tokens=MAX_JUDGE_TOKENS,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "verdict", "strict": True, "schema": schema},
            },
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
        )
        choice = response.choices[0]
        try:
            reply = json.loads(choice.message.content or "")
        except json.JSONDecodeError:
            return Verdict(
                UNJUDGED, f"No verdict in the reply (finish reason {choice.finish_reason})."
            )
        return Verdict(reply["verdict"], reply["reason"])
