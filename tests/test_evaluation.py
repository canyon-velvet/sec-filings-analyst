import json
from pathlib import Path

import pytest
from fakes.answerer import FakeAnswerer
from fakes.retriever import FakeRetriever

from sec_filings_analyst.evaluation import run_answer_eval, run_eval
from sec_filings_analyst.experiments import ORACLE_FILTER, Experiment
from sec_filings_analyst.financebench import load_questions
from sec_filings_analyst.retriever import Filter

# 00001 3M Evidence pages {60, 61} · 00002 3M {1} · 00003 AMCOR {3} (1-based, see #10)
QUESTIONS = load_questions(Path(__file__).parent / "fixtures" / "financebench.jsonl")
MMM, AMCOR = "3M_2018_10K", "AMCOR_2022_8K_dated-2022-07-01"
HITS = {
    "What was 3M's FY2018 capital expenditure?": [(MMM, 60), (MMM, 60), (MMM, 5)],  # rank 1
    "Is 3M capital intensive?": [(MMM, 7), (AMCOR, 1)],  # missed
    "What did Amcor announce?": [(MMM, 1), (AMCOR, 3)],  # rank 2: 3M's Page 1 isn't AMCOR's
}
PROVENANCE = {"commit": "abc123", "corpus": {"documents": 2, "chunks": 5}}


def baseline(retriever=None, settings=None):
    return Experiment("dense-baseline", settings or {}, retriever or FakeRetriever(HITS))


def test_a_run_saves_metrics_and_per_question_ranks_and_adds_a_results_row(tmp_path):
    retriever = FakeRetriever(HITS)

    run_eval(baseline(retriever, {"retriever": "fake"}), "dev", QUESTIONS, PROVENANCE, tmp_path)

    run = json.loads((tmp_path / "runs" / "dev" / "dense-baseline.json").read_text())
    assert retriever.ks == [50, 50, 50]  # over-fetch Chunks so 10 unique Pages can be scored
    assert run["experiment"] == "dense-baseline" and run["split"] == "dev"
    assert run["config"] == {"retriever": "fake", "fetch_k": 50}
    assert run["commit"] == "abc123"
    assert run["corpus"] == {"documents": 2, "chunks": 5}
    assert run["overall"] == {
        "hit_at_1": 1 / 3,
        "hit_at_5": 2 / 3,
        "hit_at_10": 2 / 3,
        "recall_at_10": (0.5 + 0 + 1) / 3,  # 00001 found 60 but not 61
        "mrr_at_10": (1 + 0 + 1 / 2) / 3,
        "n": 3,
    }
    assert run["by_type"]["novel-generated"]["mrr_at_10"] == 0.5
    assert run["questions"]["financebench_id_00001"] == {
        "question_type": "metrics-generated",
        "first_evidence_rank": 1,
        "evidence_pages": [[MMM, 60], [MMM, 61]],
        "top_pages": [[MMM, 60], [MMM, 5]],  # the two Chunks on Page 60 count once
    }
    assert run["questions"]["financebench_id_00002"]["first_evidence_rank"] is None
    assert (tmp_path / "RESULTS.md").read_text() == RESULTS_WITH_BASELINE


def test_a_run_counts_questions_that_got_fewer_than_10_unique_pages(tmp_path):
    ten_pages = [(MMM, 60), (MMM, 60)] + [(MMM, n) for n in range(1, 10)]  # 11 Chunks, 10 Pages
    hits = HITS | {"What was 3M's FY2018 capital expenditure?": ten_pages}

    run_eval(baseline(FakeRetriever(hits)), "dev", QUESTIONS, PROVENANCE, tmp_path)

    run = json.loads((tmp_path / "runs" / "dev" / "dense-baseline.json").read_text())
    assert run["fewer_than_10_pages"] == 2  # the other two got 2 Pages each


def test_each_run_adds_a_row_and_a_reused_experiment_and_split_is_refused(tmp_path):
    run_eval(baseline(), "dev", QUESTIONS, PROVENANCE, tmp_path)
    # The same experiment, tuned on dev, then reported on test
    run_eval(baseline(), "test", QUESTIONS[:1], PROVENANCE, tmp_path)
    saved = {p: p.read_text() for p in [*tmp_path.rglob("*.json"), tmp_path / "RESULTS.md"]}
    retriever = FakeRetriever(HITS)

    with pytest.raises(FileExistsError):
        run_eval(baseline(retriever), "test", QUESTIONS, PROVENANCE, tmp_path)
    # A folder in the name could collide with another Split's run (Splits are folders too)
    with pytest.raises(ValueError, match="week2/hybrid"):
        run_eval(Experiment("week2/hybrid", {}, retriever), "dev", QUESTIONS, PROVENANCE, tmp_path)

    assert retriever.ks == []
    assert {p: p.read_text() for p in saved} == saved
    table = saved[tmp_path / "RESULTS.md"]
    assert "| dense-baseline | test | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 1 |" in table
    # Its one Question is metrics-generated
    assert "| dense-baseline | test | – | 1.00 | – |" in table


def test_an_oracle_experiment_filters_by_the_question_s_company_doc_type_and_year(tmp_path):
    oracle, plain = FakeRetriever(HITS), FakeRetriever(HITS)

    oracle_experiment = Experiment("oracle", {"filter": ORACLE_FILTER}, oracle)
    run_eval(oracle_experiment, "dev", QUESTIONS, PROVENANCE, tmp_path)
    run_eval(baseline(plain), "dev", QUESTIONS, PROVENANCE, tmp_path)

    mmm_2018 = Filter(company="3M", doc_type="10-K", fiscal_year=2018)
    assert oracle.filters == [mmm_2018, mmm_2018, Filter("AMCOR", "8-K", 2022)]
    assert plain.filters == [None, None, None]


def test_an_experiment_runs_only_on_chunks_with_the_header_format_it_expects(tmp_path):
    headered = PROVENANCE | {"corpus": PROVENANCE["corpus"] | {"header_format": "{company}"}}
    retriever = FakeRetriever(HITS)

    # dense-baseline expects bare Chunks: run on headered ones, its name would hide that
    with pytest.raises(ValueError, match="dense-baseline expects Chunks with no headers, but the"):
        run_eval(baseline(retriever), "dev", QUESTIONS, headered, tmp_path)
    assert retriever.ks == []  # refused before any search

    headers = Experiment("dense-headers", {"header_format": "{company}"}, retriever)
    run_eval(headers, "dev", QUESTIONS, headered, tmp_path)
    assert retriever.ks == [50, 50, 50]


def YES(summary: str) -> bool:
    return True


REPLIES = {
    "What was 3M's FY2018 capital expenditure?": "Capex was $1,577M [1].",  # Page 60: a hit
    "Is 3M capital intensive?": "Not by its capex [3].",  # 2 Chunks came back: [3] is invalid
    "What did Amcor announce?": "A merger [1] [2].",  # 3M's Page 1 misses; AMCOR's Page 3 hits
}


def test_an_answer_run_commits_citations_and_metrics_but_keeps_answer_text_local(tmp_path):
    retriever, answerer = FakeRetriever(HITS), FakeAnswerer(REPLIES)
    run_eval(baseline(), "dev", QUESTIONS, PROVENANCE, tmp_path)

    run_answer_eval(baseline(retriever), "dev", QUESTIONS, PROVENANCE, answerer, YES, tmp_path)

    assert retriever.ks == [10, 10, 10]  # the top 10 Chunks go to the Answerer
    assert [len(chunks) for _, chunks in answerer.calls] == [3, 2, 2]
    committed = (tmp_path / "answer_runs" / "dev" / "dense-baseline.json").read_text()
    run = json.loads(committed)
    assert run["config"] == {"answer_model": "fake-answerer", "answer_chunks": 10}
    assert (run["commit"], run["corpus"]) == ("abc123", {"documents": 2, "chunks": 5})
    assert run["overall"] == {"citation_hit_rate": 2 / 3, "invalid_citations": 1, "n": 3}
    assert run["by_type"]["domain-relevant"] == {
        "citation_hit_rate": 0.0,
        "invalid_citations": 1,
        "n": 1,
    }
    assert run["questions"]["financebench_id_00003"] == {
        "question_type": "novel-generated",
        "evidence_pages": [[AMCOR, 3]],
        "cited_pages": [[MMM, 1], [AMCOR, 3]],
        "invalid_citations": 0,
        "citation_hit": True,
    }
    assert not any(reply.split(" [")[0] in committed for reply in REPLIES.values())
    local = (tmp_path / "answer_runs" / "dev" / "dense-baseline.local.jsonl").read_text()
    assert json.loads(local.splitlines()[1]) == {
        "id": "financebench_id_00002",
        "answer": "Not by its capex.",
    }
    results = (tmp_path / "RESULTS.md").read_text()
    assert results.startswith(RESULTS_WITH_BASELINE)  # the retrieval tables stay
    assert "| dense-baseline | dev | fake-answerer | 0.67 | 1 | 3 |" in results


def test_an_answer_run_is_refused_before_any_call_for_a_reused_or_invalid_name(tmp_path):
    run_answer_eval(baseline(), "dev", QUESTIONS, PROVENANCE, FakeAnswerer(REPLIES), YES, tmp_path)
    saved = {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()}
    retriever, answerer = FakeRetriever(HITS), FakeAnswerer(REPLIES)

    with pytest.raises(FileExistsError):
        run_answer_eval(baseline(retriever), "dev", QUESTIONS, PROVENANCE, answerer, YES, tmp_path)
    with pytest.raises(ValueError, match="week2/hybrid"):
        experiment = Experiment("week2/hybrid", {}, retriever)
        run_answer_eval(experiment, "dev", QUESTIONS, PROVENANCE, answerer, YES, tmp_path)

    assert (retriever.ks, answerer.calls) == ([], [])
    assert {p: p.read_text() for p in saved} == saved


def test_an_answer_run_asks_about_its_cost_ceiling_before_any_call_and_a_no_stops_it(tmp_path):
    retriever, answerer = FakeRetriever(HITS), FakeAnswerer(REPLIES)
    asked = []

    def decline(summary: str) -> bool:
        asked.append((summary, list(retriever.ks), list(answerer.calls)))
        return False

    run_answer_eval(baseline(retriever), "dev", QUESTIONS, PROVENANCE, answerer, decline, tmp_path)

    ((summary, ks_then, calls_then),) = asked
    assert (ks_then, calls_then) == ([], [])  # asked before any search or Answer
    # Each Answer's output is capped at 1,000 tokens; input counts each Chunk at its 512 cap
    assert "Answer 3 Questions with fake-answerer" in summary
    assert "3,000 output tokens" in summary and "$" in summary
    assert (retriever.ks, answerer.calls) == ([], [])
    assert list(tmp_path.rglob("*")) == []


RESULTS_WITH_BASELINE = """\
# Retrieval results

Generated by `make eval` from `eval/runs/`; don't edit by hand.

An Experiment whose settings set an oracle filter searches only each Question's company,
Doc type and Fiscal year, which no user knows: an upper bound, not a result.

| Experiment | Split | Hit@1 | Hit@5 | Hit@10 | Recall@10 | MRR@10 | n |
|---|---|---|---|---|---|---|---|
| dense-baseline | dev | 0.33 | 0.67 | 0.67 | 0.50 | 0.50 | 3 |

## Hit@5 by question type

| Experiment | Split | domain-relevant | metrics-generated | novel-generated |
|---|---|---|---|---|
| dense-baseline | dev | 0.00 | 1.00 | 1.00 |
"""
