import pytest
from fakes.retriever import FakeRetriever

from sec_filings_analyst.retriever import Filter, HybridSearcher

Q = "What was ACME's FY2020 capex?"


def pages(results):
    return [(r.chunk.document.name, r.chunk.page) for r in results]


def test_a_chunk_ranked_high_by_only_one_searcher_rises_above_chunks_ranked_low():
    dense = FakeRetriever({Q: [("A", 1), ("A", 2), ("A", 3)]})
    keyword = FakeRetriever({Q: [("B", 9), ("A", 1)]})  # dense never found B's Page 9

    results = HybridSearcher([dense, keyword], candidates=10).search(Q, k=4)

    # A1: 1/61 + 1/62 · B9: 1/61 · A2: 1/62 · A3: 1/63
    assert pages(results) == [("A", 1), ("B", 9), ("A", 2), ("A", 3)]


def test_the_same_chunk_from_both_searchers_is_one_result_with_the_summed_score():
    dense = FakeRetriever({Q: [("A", 1)]})
    keyword = FakeRetriever({Q: [("A", 1)]})

    results = HybridSearcher([dense, keyword], candidates=10).search(Q, k=5)

    assert pages(results) == [("A", 1)]
    assert results[0].score == pytest.approx(0.03279, abs=1e-5)  # 2/61


def test_tied_chunks_keep_the_earlier_searcher_s_order():
    dense = FakeRetriever({Q: [("A", 1)]})
    keyword = FakeRetriever({Q: [("B", 9)]})  # both 1/61

    assert pages(HybridSearcher([dense, keyword], candidates=10).search(Q, k=2)) == [
        ("A", 1),
        ("B", 9),
    ]
    assert pages(HybridSearcher([keyword, dense], candidates=10).search(Q, k=2)) == [
        ("B", 9),
        ("A", 1),
    ]


def test_each_searcher_is_asked_for_max_of_k_and_the_candidates_and_at_most_k_come_back():
    dense = FakeRetriever({Q: [("A", 1), ("A", 2), ("A", 3)]})
    keyword = FakeRetriever({Q: [("B", 1), ("B", 2), ("B", 3)]})
    hybrid = HybridSearcher([dense, keyword], candidates=3)

    assert len(hybrid.search(Q, k=2)) == 2
    assert len(hybrid.search(Q, k=5)) == 5  # not capped at the candidates

    assert dense.ks == [3, 5] and keyword.ks == [3, 5]


def test_the_filter_is_passed_to_each_searcher():
    dense, keyword = FakeRetriever({Q: [("A", 1)]}), FakeRetriever({Q: [("A", 1)]})
    acme_2020 = Filter(company="ACME", fiscal_year=2020)

    HybridSearcher([dense, keyword], candidates=10).search(Q, k=5, filter=acme_2020)

    assert dense.filters == [acme_2020] and keyword.filters == [acme_2020]
