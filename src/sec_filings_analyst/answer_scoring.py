"""Answer scoring: whether each Answer cites an Evidence page, and how many of its Citations
matched no Chunk it was given."""

from dataclasses import dataclass
from statistics import mean

from sec_filings_analyst.scoring import Page


@dataclass(frozen=True)
class Answered:
    """One Question's Answer as scoring sees it: the Pages it cites and its Evidence pages."""

    question_type: str
    cited: list[Page]
    invalid_citations: int
    evidence: set[Page]


@dataclass(frozen=True)
class AnswerMetrics:
    citation_hit_rate: float  # share of Answers citing at least one Evidence page
    invalid_citations: int  # total over the Answers
    n: int


@dataclass(frozen=True)
class AnswerScores:
    citation_hits: dict[str, bool]  # per Question id
    overall: AnswerMetrics
    by_type: dict[str, AnswerMetrics]  # keyed by question type


def score_answers(answers: dict[str, Answered]) -> AnswerScores:
    hits = {qid: bool(set(a.cited) & a.evidence) for qid, a in answers.items()}

    def aggregate(qids: list[str]) -> AnswerMetrics:
        invalid = sum(answers[q].invalid_citations for q in qids)
        return AnswerMetrics(mean(float(hits[q]) for q in qids), invalid, len(qids))

    types = sorted({a.question_type for a in answers.values()})
    by_type = {t: aggregate([q for q, a in answers.items() if a.question_type == t]) for t in types}
    return AnswerScores(hits, aggregate(list(answers)), by_type)
