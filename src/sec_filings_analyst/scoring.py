"""Retrieval scoring: how well ranked Pages cover each Question's Evidence pages."""

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class Page:
    document: str
    number: int  # 1-based


@dataclass(frozen=True)
class Retrieval:
    """One Question's ranked retrieved Pages (may repeat) and its Evidence pages."""

    question_type: str
    ranked: list[Page]
    evidence: set[Page]


@dataclass(frozen=True)
class QuestionScore:
    first_evidence_rank: int | None  # None = no Evidence page retrieved
    hit_at_1: float
    hit_at_5: float
    hit_at_10: float
    recall_at_10: float
    rr_at_10: float  # reciprocal rank


@dataclass(frozen=True)
class Metrics:
    hit_at_1: float
    hit_at_5: float
    hit_at_10: float
    recall_at_10: float
    mrr_at_10: float
    n: int


@dataclass(frozen=True)
class Scores:
    per_question: dict[str, QuestionScore]
    overall: Metrics
    by_type: dict[str, Metrics]  # keyed by question type


def score(retrievals: dict[str, Retrieval]) -> Scores:
    per_question = {qid: _score_question(r) for qid, r in retrievals.items()}
    types = {r.question_type for r in retrievals.values()}
    by_type = {
        t: _aggregate([per_question[q] for q, r in retrievals.items() if r.question_type == t])
        for t in sorted(types)
    }
    return Scores(per_question, _aggregate(list(per_question.values())), by_type)


def _score_question(retrieval: Retrieval) -> QuestionScore:
    unique = list(dict.fromkeys(retrieval.ranked))  # keeps each Page's first-seen rank
    ranks = [i for i, page in enumerate(unique, 1) if page in retrieval.evidence]
    first = ranks[0] if ranks else None
    top_10 = set(unique[:10]) & retrieval.evidence

    def hit(k):
        return float(first is not None and first <= k)

    return QuestionScore(
        first_evidence_rank=first,
        hit_at_1=hit(1),
        hit_at_5=hit(5),
        hit_at_10=hit(10),
        recall_at_10=len(top_10) / len(retrieval.evidence),
        rr_at_10=1 / first if hit(10) else 0.0,
    )


def _aggregate(scores: list[QuestionScore]) -> Metrics:
    return Metrics(
        hit_at_1=mean(s.hit_at_1 for s in scores),
        hit_at_5=mean(s.hit_at_5 for s in scores),
        hit_at_10=mean(s.hit_at_10 for s in scores),
        recall_at_10=mean(s.recall_at_10 for s in scores),
        mrr_at_10=mean(s.rr_at_10 for s in scores),
        n=len(scores),
    )
