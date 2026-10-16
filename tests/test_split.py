import json
from collections import Counter

import pytest

from sec_filings_analyst.documents import Document
from sec_filings_analyst.financebench import Question
from sec_filings_analyst.split import Split, make_split, write_split

ACME = Document(name="ACME_2023_10K", company="ACME", doc_type="10-K", fiscal_year=2023)
TYPES = ["domain-relevant", "metrics-generated", "novel-generated"]
# 150 Questions, 50 of each type, like the FinanceBench open sample.
QUESTIONS = [
    Question(f"q{i:03}", TYPES[i % 3], ACME, "text", "answer", frozenset({1})) for i in range(150)
]
TYPE_OF = {q.id: q.question_type for q in QUESTIONS}


def test_dev_takes_50_questions_stratified_by_question_type():
    split = make_split(QUESTIONS, dev_size=50, seed=7)

    # 50 × 50/150 = 16.67 per type: 16 each, and the 2 left over go to the first two types.
    assert Counter(TYPE_OF[q] for q in split.dev) == {
        "domain-relevant": 17,
        "metrics-generated": 17,
        "novel-generated": 16,
    }
    assert len(split.test) == 100
    assert set(split.dev) | set(split.test) == set(TYPE_OF)
    assert not set(split.dev) & set(split.test)


def test_the_same_seed_gives_the_same_split_whatever_the_question_order():
    split = make_split(QUESTIONS, dev_size=50, seed=7)

    assert make_split(QUESTIONS[::-1], dev_size=50, seed=7) == split
    assert make_split(QUESTIONS, dev_size=50, seed=8) != split


def test_a_written_split_is_never_overwritten(tmp_path):
    path = tmp_path / "splits" / "financebench_v1.json"
    write_split(Split(dev=["q1"], test=["q2", "q3"]), path)

    with pytest.raises(FileExistsError):
        write_split(Split(dev=["q2"], test=["q1", "q3"]), path)

    assert json.loads(path.read_text()) == {"dev": ["q1"], "test": ["q2", "q3"]}
