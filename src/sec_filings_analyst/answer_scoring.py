"""Answer scoring: the Judge's verdicts, whether each Answer cites an Evidence page, how many of
its Citations matched no Chunk it was given, and, for numeric Questions, whether it states
FinanceBench's number and whether the Judge agrees."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import mean

from sec_filings_analyst.scoring import Page

TOLERANCE = 0.01  # relative
SCALES = {None: 1, "%": 1, "thousand": 1e3, "million": 1e6, "billion": 1e9}
# A number with its commas and an optional scale: "1,577", "65.4%", "1.58 billion"; not part of a
# word or a Doc type ("FY2017", "Q3", "10-K")
_NUMBER = re.compile(
    r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?!\d|-[a-z])\s*(%|thousand|million|billion)?",
    re.IGNORECASE,
)
_GOLD = re.compile(rf"-?\$?-?{_NUMBER.pattern}", re.IGNORECASE)  # the whole answer, e.g. "-$0.40"
_MARKER = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")


@dataclass(frozen=True)
class Answered:
    """One Question's Answer as scoring sees it: the Pages it cites and its Evidence pages."""

    question_type: str
    cited: list[Page]
    invalid_citations: int
    evidence: set[Page]
    numeric_match: bool | None  # None: FinanceBench's answer isn't a single number
    correctness: str  # the Judge's: correct, incorrect, refused, or unjudged
    supported: bool | None  # the Judge's faithfulness verdict; None if refused, empty or unjudged
    unjudged: int  # Judge replies without a verdict (0–2)


@dataclass(frozen=True)
class AnswerMetrics:
    accuracy: float  # share of Answers the Judge grades correct
    refusal_rate: float  # share it grades refused, apart from incorrect
    faithfulness_rate: float | None  # share of non-refusals supported by their Citations
    disagreement_rate: float | None  # of numeric Answers graded correct or incorrect, the share
    # where the Judge's grade and the numeric check differ
    citation_hit_rate: float  # share of Answers citing at least one Evidence page
    invalid_citations: int  # total over the Answers
    unjudged: int  # Judge replies without a verdict, in total
    numeric_accuracy: float | None  # share of numeric Questions matched; None without any
    numeric_n: int  # numeric Questions
    n: int


@dataclass(frozen=True)
class AnswerScores:
    citation_hits: dict[str, bool]  # per Question id
    overall: AnswerMetrics
    by_type: dict[str, AnswerMetrics]  # keyed by question type


def score_answers(answers: dict[str, Answered]) -> AnswerScores:
    hits = {qid: bool(set(a.cited) & a.evidence) for qid, a in answers.items()}

    def aggregate(qids: list[str]) -> AnswerMetrics:
        numeric = [answers[q] for q in qids if answers[q].numeric_match is not None]
        graded = [a for a in numeric if a.correctness in ("correct", "incorrect")]
        disagree = [(a.correctness == "correct") != a.numeric_match for a in graded]
        supported = [answers[q].supported for q in qids if answers[q].supported is not None]
        return AnswerMetrics(
            accuracy=_share(answers[q].correctness == "correct" for q in qids),
            refusal_rate=_share(answers[q].correctness == "refused" for q in qids),
            faithfulness_rate=_share(supported) if supported else None,
            disagreement_rate=_share(disagree) if graded else None,
            citation_hit_rate=_share(hits[q] for q in qids),
            invalid_citations=sum(answers[q].invalid_citations for q in qids),
            unjudged=sum(answers[q].unjudged for q in qids),
            numeric_accuracy=_share(a.numeric_match for a in numeric) if numeric else None,
            numeric_n=len(numeric),
            n=len(qids),
        )

    types = sorted({a.question_type for a in answers.values()})
    by_type = {t: aggregate([q for q, a in answers.items() if a.question_type == t]) for t in types}
    return AnswerScores(hits, aggregate(list(answers)), by_type)


def _share(flags: Iterable[bool]) -> float:
    return mean(float(flag) for flag in flags)


def numeric_match(gold: str, answer: str) -> bool | None:
    """Whether some number in the Answer is within TOLERANCE of FinanceBench's answer, or None
    when that isn't a single number. Sizes only: an Answer often gives the sign in words ("fell
    3.7%"). A gold number with no scale word or % matches at any power-of-1000 scale, since its
    unit is often only in the Question ("in USD millions")."""
    match = _GOLD.fullmatch(gold.strip())
    if not match:
        return None
    expected = _value(match)
    scales = [1.0] if match[3] else [1000.0**k for k in range(-3, 4)]
    numbers = []
    for number in _NUMBER.finditer(_MARKER.sub("", answer)):
        numbers.append(_value(number))
        if number[3] == "%":  # also a ratio: "1%" states FinanceBench's "0.01"
            numbers.append(_value(number) / 100)
    return any(abs(n - expected * s) <= TOLERANCE * expected * s for n in numbers for s in scales)


def _value(match: re.Match) -> float:
    number, decimals, scale = match.groups()[-3:]
    return float(number.replace(",", "") + (decimals or "")) * SCALES[scale and scale.lower()]
