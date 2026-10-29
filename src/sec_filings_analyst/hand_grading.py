"""Hand grading: the developer grades a sample of an answer run's Answers blind, so the Judge's
correctness verdicts can be checked against a person's. The sheet holds FinanceBench text and
stays local; only the grades, by Question id, are committed."""

import re
from dataclasses import dataclass
from statistics import mean

from sec_filings_analyst.judge import CORRECTNESS
from sec_filings_analyst.scoring import Page

SAMPLE_SIZE = 20  # of dev's 50 Questions, by type as make_split draws them: 7 / 7 / 6
_HEADING = re.compile(r"^## (\d+)\. (\S+) \(", re.MULTILINE)
_GRADE = re.compile(r"^Grade:(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class SheetItem:
    question_id: str
    question_type: str
    question: str
    expected: str  # FinanceBench's answer
    answer: str
    cited: list[Page]


@dataclass(frozen=True)
class Agreement:
    rate: float  # share of hand-graded Answers whose Judge correctness verdict is the same
    by_type: dict[str, float]
    disagreements: list[str]  # Question ids, sorted
    n: int  # hand-graded Answers


def sheet(answer_run: str, items: list[SheetItem]) -> str:
    """A Markdown sheet with an empty Grade: line per item and no Judge verdicts, so grading is
    blind. Texts are quoted (> ), so nothing in them can start a heading or a Grade: line."""
    lines = [
        f"# Hand grades: {answer_run}",
        "",
        f"After each Grade:, write {_labels()}, against FinanceBench's answer:",
        "- correct: it gives FinanceBench's figure or conclusion (rounding, other units are fine)",
        "- incorrect: a different figure or conclusion, or it doesn't answer what was asked",
        "- refused: it says it can't find the answer and gives none",
    ]
    for n, item in enumerate(items, 1):
        cited = ", ".join(f"{p.document_name} p{p.number}" for p in item.cited) or "nothing"
        lines += ["", f"## {n}. {item.question_id} ({item.question_type})", ""]
        for label, text in [
            ("Question", item.question),
            ("FinanceBench", item.expected),
            ("Answer", item.answer),
        ]:
            lines += [f"**{label}:**", *(f"> {line}" for line in text.splitlines()), ""]
        lines += [f"**Cited:** {cited}", "", "Grade: "]
    return "\n".join(lines) + "\n"


def read_grades(text: str) -> dict[str, str]:
    """The grades by Question id. Raises ValueError, naming the item, for a missing grade or one
    that isn't a correctness label, and for a sheet with no items or an item twice."""
    headings = list(_HEADING.finditer(text))
    if not headings:
        raise ValueError("the sheet has no items")
    grades = {}
    for heading, following in zip(headings, [*headings[1:], None], strict=True):
        item = text[heading.end() : following.start() if following else len(text)]
        name = f"{heading[1]}. {heading[2]}"
        if heading[2] in grades:
            raise ValueError(f"{name} is graded twice")
        grade_line = _GRADE.search(item)
        grade = grade_line[1].strip().lower() if grade_line else ""
        if not grade:
            raise ValueError(f"{name} has no grade")
        if grade not in CORRECTNESS:
            raise ValueError(f"{name}: {grade!r} isn't {_labels()}")
        grades[heading[2]] = grade
    return grades


def judge_agreement(grades: dict[str, str], run_questions: dict[str, dict]) -> Agreement:
    """How often the Judge's correctness verdicts, as an answer run commits them per Question,
    match the hand grades."""
    agrees = {q: run_questions[q]["correctness"] == grade for q, grade in grades.items()}
    types = sorted({run_questions[q]["question_type"] for q in grades})
    by_type = {
        t: mean(float(a) for q, a in agrees.items() if run_questions[q]["question_type"] == t)
        for t in types
    }
    disagreements = sorted(q for q, a in agrees.items() if not a)
    return Agreement(mean(map(float, agrees.values())), by_type, disagreements, len(grades))


def _labels() -> str:
    return f"{', '.join(CORRECTNESS[:-1])} or {CORRECTNESS[-1]}"


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    from sec_filings_analyst.evaluation import write_results
    from sec_filings_analyst.financebench import load_questions
    from sec_filings_analyst.split import SEED, make_split

    command = sys.argv[1]  # sheet, then grades once the sheet is filled in
    answer_run = "financebench_v1/dev/dense-headers"
    run_file = Path("eval/answer_runs") / f"{answer_run}.json"
    sheet_file = Path("eval/hand_grades") / f"{answer_run}.sheet.local.md"
    if command == "sheet":
        dev = set(json.loads(Path("eval/splits/financebench_v1.json").read_text("utf-8"))["dev"])
        all_questions = load_questions(Path("data/financebench/financebench_merged.jsonl"))
        questions = {q.id: q for q in all_questions if q.id in dev}
        sample = make_split(list(questions.values()), SAMPLE_SIZE, SEED).dev
        run = json.loads(run_file.read_text(encoding="utf-8"))["questions"]
        with run_file.with_suffix(".local.jsonl").open(encoding="utf-8") as rows:
            answers = {row["id"]: row["answer"] for row in map(json.loads, rows)}
        items = [
            SheetItem(
                q,
                questions[q].question_type,
                questions[q].text,
                questions[q].answer,
                answers[q],
                [Page(*p) for p in run[q]["cited_pages"]],
            )
            for q in sample
        ]
        sheet_file.parent.mkdir(parents=True, exist_ok=True)
        with sheet_file.open("x", encoding="utf-8") as file:  # never overwrites your grades
            file.write(sheet(answer_run, items))
        print(f"Grade the {len(items)} Answers in {sheet_file}, then run make judge-agreement")
    else:
        grades = read_grades(sheet_file.read_text(encoding="utf-8"))
        with sheet_file.with_name(f"{run_file.stem}.json").open("x", encoding="utf-8") as file:
            json.dump(grades, file, indent=2)
            file.write("\n")
        write_results(Path("eval"))
        print("Judge agreement added to eval/RESULTS.md")
