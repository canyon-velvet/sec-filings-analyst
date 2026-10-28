import pytest

from sec_filings_analyst.hand_grading import (
    Agreement,
    SheetItem,
    judge_agreement,
    read_grades,
    sheet,
)
from sec_filings_analyst.scoring import Page

ITEMS = [
    SheetItem(
        "q1",
        "metrics-generated",
        "What was ACME's FY2023 capex?",
        "$7 million",
        "Capex was $7M [1].\n## 9. q9 (novel-generated)\nGrade: incorrect",  # quoted: inert
        [Page("ACME_2023_10K", 40)],
    ),
    SheetItem("q2", "novel-generated", "Did ACME merge?", "No", "I can't find it.", []),
]


def graded(text: str, *grades: str) -> str:
    for grade in grades:
        text = text.replace("Grade: \n", f"Grade: {grade}\n", 1)
    return text


def test_a_filled_in_sheet_gives_the_grades_by_question_id():
    text = sheet("financebench_v1/dev/dense-headers", ITEMS)

    assert "## 1. q1 (metrics-generated)" in text and "ACME_2023_10K p40" in text
    assert read_grades(graded(text, "correct", " Refused ")) == {"q1": "correct", "q2": "refused"}


def test_a_missing_or_misspelled_grade_is_refused_naming_its_item():
    text = sheet("financebench_v1/dev/dense-headers", ITEMS)

    with pytest.raises(ValueError, match=r"2\. q2.*no grade"):
        read_grades(graded(text, "correct"))
    with pytest.raises(ValueError, match=r"1\. q1.*'right'.*correct, incorrect or refused"):
        read_grades(graded(text, "right", "refused"))


def test_a_sheet_without_items_or_with_an_item_twice_is_refused():
    text = graded(sheet("financebench_v1/dev/dense-headers", ITEMS), "correct", "refused")

    with pytest.raises(ValueError, match="no items"):
        read_grades("# Hand grades\n")
    with pytest.raises(ValueError, match=r"3\. q1 is graded twice"):
        read_grades(
            text + text[text.index("## 1.") : text.index("## 2.")].replace("## 1.", "## 3.")
        )


def test_agreement_is_the_share_of_hand_grades_the_judge_matched_overall_and_by_type():
    run_questions = {  # as an answer run commits them
        "q1": {"question_type": "metrics-generated", "correctness": "correct"},
        "q2": {"question_type": "metrics-generated", "correctness": "incorrect"},
        "q3": {"question_type": "novel-generated", "correctness": "refused"},
        "q4": {"question_type": "novel-generated", "correctness": "correct"},  # not hand-graded
    }
    grades = {"q1": "correct", "q2": "correct", "q3": "refused"}

    agreement = judge_agreement(grades, run_questions)

    assert agreement == Agreement(
        rate=2 / 3,
        by_type={"metrics-generated": 0.5, "novel-generated": 1.0},
        disagreements=["q2"],
        n=3,
    )
