import pytest

from sec_filings_analyst.bm25 import Bm25


def test_a_rare_shared_term_outranks_a_common_term_repeated_many_times():
    # Like Exhibit 21 (a subsidiary list) saying "company" on every line
    index = Bm25({"compani": {1: 20, 2: 1, 3: 1, 4: 1}, "capex": {2: 1}})

    top = index.top(["compani", "capex"], k=2)

    assert [chunk for chunk, _ in top] == [2, 1]


def test_scores_follow_bm25_and_chunks_without_a_query_term_are_left_out():
    index = Bm25({"debt": {7: 2}, "cash": {8: 1}})

    # N=2, df=1: IDF = ln(1 + 1.5/1.5) = ln 2 · Chunk 7: tf=2, length 2, average length 1.5:
    # 2·2.2 / (2 + 1.2·(0.25 + 0.75·2/1.5)) = 4.4/3.5 → 0.6931 · 1.2571 = 0.8714
    assert index.top(["debt", "unicorn"], k=5) == [(7, pytest.approx(0.8714, abs=1e-4))]
