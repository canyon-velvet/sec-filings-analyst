import pytest

from sec_filings_analyst.scoring import Page, Retrieval, score

A1, A2, A3 = Page("AMD_2022_10K", 1), Page("AMD_2022_10K", 2), Page("AMD_2022_10K", 3)
B4 = Page("3M_2018_10K", 4)


def test_first_rank_hit():
    scores = score({"q1": Retrieval("domain-relevant", ranked=[A1, B4], evidence={A1})})

    assert scores.per_question["q1"].first_evidence_rank == 1
    overall = scores.overall
    assert (overall.hit_at_1, overall.hit_at_5, overall.hit_at_10) == (1.0, 1.0, 1.0)
    assert overall.recall_at_10 == 1.0
    assert overall.mrr_at_10 == 1.0


def test_hit_at_rank_3():
    scores = score({"q1": Retrieval("domain-relevant", ranked=[A1, B4, A2], evidence={A2})})

    assert scores.per_question["q1"].first_evidence_rank == 3
    overall = scores.overall
    assert (overall.hit_at_1, overall.hit_at_5, overall.hit_at_10) == (0.0, 1.0, 1.0)
    assert overall.mrr_at_10 == 1 / 3


def test_miss():
    scores = score({"q1": Retrieval("domain-relevant", ranked=[A1, B4], evidence={A3})})

    assert scores.per_question["q1"].first_evidence_rank is None
    overall = scores.overall
    assert (overall.hit_at_1, overall.hit_at_5, overall.hit_at_10) == (0.0, 0.0, 0.0)
    assert overall.recall_at_10 == 0.0
    assert overall.mrr_at_10 == 0.0


def test_partial_recall_with_two_evidence_pages():
    scores = score({"q1": Retrieval("metrics-generated", ranked=[A1, B4], evidence={A1, A3})})

    assert scores.overall.recall_at_10 == 0.5


def test_duplicate_pages_collapse_to_their_first_rank():
    # Three Chunks from Page A1 count as one ranked Page, so A2 ranks 2nd, not 4th.
    ranked = [A1, A1, A1, A2]

    scores = score({"q1": Retrieval("domain-relevant", ranked=ranked, evidence={A2})})

    assert scores.per_question["q1"].first_evidence_rank == 2
    assert scores.overall.mrr_at_10 == 0.5


def test_aggregates_overall_and_per_question_type():
    scores = score(
        {
            "q1": Retrieval("domain-relevant", ranked=[A1], evidence={A1}),  # rank 1
            "q2": Retrieval("domain-relevant", ranked=[B4], evidence={A1}),  # miss
            "q3": Retrieval("novel-generated", ranked=[A1, B4, A2], evidence={A2}),  # rank 3
        }
    )

    domain = scores.by_type["domain-relevant"]
    assert (domain.hit_at_1, domain.mrr_at_10, domain.n) == (0.5, 0.5, 2)
    novel = scores.by_type["novel-generated"]
    assert (novel.hit_at_1, novel.hit_at_5, novel.n) == (0.0, 1.0, 1)
    assert novel.mrr_at_10 == pytest.approx(1 / 3)
    overall = scores.overall
    assert (overall.hit_at_5, overall.n) == (pytest.approx(2 / 3), 3)
    assert overall.mrr_at_10 == pytest.approx(4 / 9)  # (1 + 0 + 1/3) / 3
