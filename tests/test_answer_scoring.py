from sec_filings_analyst.answer_scoring import Answered, AnswerMetrics, numeric_match, score_answers
from sec_filings_analyst.scoring import Page

MMM, AMCOR = "3M_2018_10K", "AMCOR_2022_8K"


def test_answers_score_citation_hits_invalid_citations_and_the_numeric_check_of_numeric_questions():
    answers = {
        "q1": Answered(
            "metrics-generated", [Page(MMM, 5), Page(MMM, 60)], 0, {Page(MMM, 60)}, True
        ),
        # Page 60 of another Document, and another Page of the right one: both misses
        "q2": Answered(
            "metrics-generated", [Page(AMCOR, 60), Page(MMM, 61)], 1, {Page(MMM, 60)}, False
        ),
        "q3": Answered("novel-generated", [], 2, {Page(AMCOR, 3)}, None),  # cites nothing valid
    }

    scores = score_answers(answers)

    assert scores.citation_hits == {"q1": True, "q2": False, "q3": False}
    # the numeric check counts only the numeric Questions, q1 and q2
    assert scores.overall == AnswerMetrics(
        citation_hit_rate=1 / 3, invalid_citations=3, numeric_accuracy=0.5, numeric_n=2, n=3
    )
    assert scores.by_type == {
        "metrics-generated": AnswerMetrics(0.5, 1, numeric_accuracy=0.5, numeric_n=2, n=2),
        "novel-generated": AnswerMetrics(0.0, 2, numeric_accuracy=None, numeric_n=0, n=1),
    }


def test_dollars_percents_commas_and_scale_words_parse_and_unitless_gold_matches_at_any_scale():
    assert numeric_match("$1,577 million", "Capex was $1,577 million [2].")
    assert numeric_match("65.4%", "The gross margin was 65.4% [1].")
    assert numeric_match("-0.02", "A loss of $(0.02) per share [1].")  # sign isn't compared
    # FinanceBench's "$1577.00" is in USD millions but says so only in the Question
    assert numeric_match("$1577.00", "Capex was $1.58 billion [3].")


def test_a_number_matches_within_1_percent_and_markers_and_percents_are_never_rescaled():
    assert numeric_match("100", "It was 101.")
    assert not numeric_match("100", "It was 101.1.")
    assert not numeric_match("$1,577 million", "Capex was $1.6 billion.")  # 1.5% off
    assert not numeric_match("65.4%", "The gross margin was 0.0654.")
    assert not numeric_match("1", "The filing doesn't say [1].")


def test_a_financebench_answer_that_isn_t_a_single_number_isn_t_checked():
    assert numeric_match("Yes. It decreased.", "Yes, it decreased by 3% [1].") is None
    assert numeric_match("$400,000,000 increase.", "It rose $400 million [2].") is None


def test_numbers_in_doc_types_and_fiscal_years_don_t_count_and_a_percent_is_also_a_ratio():
    assert not numeric_match("0.01", "Coca-Cola's FY2017 10-K and Q3 10-Q don't give it [1].")
    assert numeric_match("$1577.00", "Capex was $1,577M [1].")
    assert numeric_match("0.01", "Return on assets was 1% [2].")
    assert numeric_match("0.8", "The payout ratio was 80%.")
