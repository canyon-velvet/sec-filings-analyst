from sec_filings_analyst.answer_scoring import Answered, AnswerMetrics, score_answers
from sec_filings_analyst.scoring import Page

MMM, AMCOR = "3M_2018_10K", "AMCOR_2022_8K"


def test_an_answer_hits_when_any_cited_page_is_an_evidence_page_and_invalid_ones_add_up():
    answers = {
        "q1": Answered("metrics-generated", [Page(MMM, 5), Page(MMM, 60)], 0, {Page(MMM, 60)}),
        # Page 60 of another Document, and another Page of the right one: both misses
        "q2": Answered("metrics-generated", [Page(AMCOR, 60), Page(MMM, 61)], 1, {Page(MMM, 60)}),
        "q3": Answered("novel-generated", [], 2, {Page(AMCOR, 3)}),  # cites nothing valid
    }

    scores = score_answers(answers)

    assert scores.citation_hits == {"q1": True, "q2": False, "q3": False}
    assert scores.overall == AnswerMetrics(citation_hit_rate=1 / 3, invalid_citations=3, n=3)
    assert scores.by_type == {
        "metrics-generated": AnswerMetrics(citation_hit_rate=0.5, invalid_citations=1, n=2),
        "novel-generated": AnswerMetrics(citation_hit_rate=0.0, invalid_citations=2, n=1),
    }
