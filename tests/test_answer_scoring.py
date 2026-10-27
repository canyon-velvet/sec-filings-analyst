from sec_filings_analyst.answer_scoring import Answered, AnswerMetrics, numeric_match, score_answers
from sec_filings_analyst.scoring import Page

MMM, AMCOR = "3M_2018_10K", "AMCOR_2022_8K"


def answered(question_type, correctness, supported, numeric=None, invalid=0, unjudged=0, **pages):
    cited, evidence = pages.get("cited", []), pages.get("evidence", set())
    return Answered(
        question_type=question_type,
        cited=cited,
        invalid_citations=invalid,
        evidence=evidence,
        numeric_match=numeric,
        correctness=correctness,
        supported=supported,
        unjudged=unjudged,
    )


def test_answers_score_the_judge_s_verdicts_citation_hits_and_the_numeric_check_by_type():
    answers = {
        "q1": answered(
            "metrics-generated",
            "correct",
            True,
            numeric=True,
            cited=[Page(MMM, 5), Page(MMM, 60)],
            evidence={Page(MMM, 60)},
        ),
        # Page 60 of another Document, and another Page of the right one: both misses
        "q2": answered(
            "metrics-generated",
            "incorrect",
            False,
            numeric=False,
            invalid=1,
            cited=[Page(AMCOR, 60), Page(MMM, 61)],
            evidence={Page(MMM, 60)},
        ),
        "q3": answered("novel-generated", "refused", None, invalid=2, evidence={Page(AMCOR, 3)}),
    }

    scores = score_answers(answers)

    assert scores.citation_hits == {"q1": True, "q2": False, "q3": False}
    assert scores.overall == AnswerMetrics(
        accuracy=1 / 3,
        refusal_rate=1 / 3,
        faithfulness_rate=0.5,  # of q1 and q2: a refusal isn't checked for support
        disagreement_rate=0.0,
        citation_hit_rate=1 / 3,
        invalid_citations=3,
        unjudged=0,
        numeric_accuracy=0.5,  # of q1 and q2, the numeric Questions
        numeric_n=2,
        n=3,
    )
    assert scores.by_type["novel-generated"] == AnswerMetrics(
        accuracy=0.0,
        refusal_rate=1.0,
        faithfulness_rate=None,
        disagreement_rate=None,
        citation_hit_rate=0.0,
        invalid_citations=2,
        unjudged=0,
        numeric_accuracy=None,
        numeric_n=0,
        n=1,
    )
    assert scores.by_type["metrics-generated"].accuracy == 0.5


def test_disagreement_compares_only_what_the_judge_graded_and_unjudged_verdicts_are_counted():
    answers = {
        "q1": answered("metrics-generated", "correct", True, numeric=True),
        # the Judge says incorrect, but the Answer states FinanceBench's number: a disagreement
        "q2": answered("metrics-generated", "incorrect", False, numeric=True),
        # a refusal and an unjudged Answer aren't compared with the check
        "q3": answered("metrics-generated", "refused", None, numeric=True),
        "q4": answered("metrics-generated", "unjudged", None, numeric=False, unjudged=2),
        "q5": answered("novel-generated", "correct", False),
    }

    overall = score_answers(answers).overall

    assert (overall.accuracy, overall.refusal_rate, overall.unjudged) == (0.4, 0.2, 2)
    assert overall.faithfulness_rate == 1 / 3  # of q1, q2 and q5
    assert (overall.disagreement_rate, overall.numeric_accuracy) == (0.5, 0.75)


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
