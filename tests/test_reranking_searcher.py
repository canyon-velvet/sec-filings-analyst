from fakes.retriever import FakeRetriever
from fakes.scorer import FakeScorer

from sec_filings_analyst.retriever import RerankingSearcher

Q = "What was ACME's FY2020 capex?"


def pages(results):
    return [(r.chunk.document.name, r.chunk.page) for r in results]


def test_the_top_k_come_back_in_the_scorer_s_order_with_its_scores():
    inner = FakeRetriever({Q: [("A", 1), ("A", 2), ("A", 3), ("A", 4)]})
    scorer = FakeScorer({"A page 3": 9.0, "A page 1": 2.5, "A page 4": -1.0, "A page 2": -4.0})

    results = RerankingSearcher(inner, scorer, candidates=4).search(Q, k=2)

    assert pages(results) == [("A", 3), ("A", 1)]
    assert [r.score for r in results] == [9.0, 2.5]
    assert scorer.calls == [[(Q, "A page 1"), (Q, "A page 2"), (Q, "A page 3"), (Q, "A page 4")]]


def test_the_inner_searcher_is_asked_for_max_of_k_and_the_candidates():
    inner = FakeRetriever({Q: [("A", page) for page in range(1, 9)]})
    reranker = RerankingSearcher(inner, FakeScorer({}), candidates=5)

    assert len(reranker.search(Q, k=2)) == 2  # the top 2 of 5 candidates
    assert len(reranker.search(Q, k=8)) == 8  # not capped at the candidates

    assert inner.ks == [5, 8]


def test_tied_scores_keep_the_inner_searcher_s_order():
    inner = FakeRetriever({Q: [("A", 1), ("B", 7), ("A", 2)]})
    scorer = FakeScorer({"B page 7": 1.0})  # A1 and A2 tie at 0

    results = RerankingSearcher(inner, scorer, candidates=3).search(Q, k=3)

    assert pages(results) == [("B", 7), ("A", 1), ("A", 2)]
