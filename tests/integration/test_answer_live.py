"""A local check against the real OpenAI API, about two cents: `make check-answer`. Neither
`make test` nor `make test-integration` runs it."""

import os
from pathlib import Path

import openai
import psycopg
import pytest

from sec_filings_analyst.answerer import OpenAIAnswerer
from sec_filings_analyst.embedder import OpenAIEmbedder
from sec_filings_analyst.experiments import build_experiment
from sec_filings_analyst.financebench import load_questions
from sec_filings_analyst.judge import OpenAIJudge

JSONL = Path(__file__).parents[2] / "data" / "financebench" / "financebench_merged.jsonl"
QUESTION_ID = "financebench_id_03282"  # dev, a number; dense-headers ranks its Evidence page first

pytestmark = [
    pytest.mark.integration,
    pytest.mark.live,
    pytest.mark.skipif(not JSONL.exists(), reason="needs the FinanceBench data: make data"),
    pytest.mark.skipif("OPENAI_API_KEY" not in os.environ, reason="needs OPENAI_API_KEY in .env"),
]


def test_answers_a_dev_question_citing_its_evidence_page_and_the_judge_grades_it_correct():
    (question,) = [q for q in load_questions(JSONL) if q.id == QUESTION_ID]
    client = openai.OpenAI()
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        searcher = build_experiment("dense-headers", conn, OpenAIEmbedder(client)).searcher
        chunks = [r.chunk for r in searcher.search(question.text, k=10)]

    answer = OpenAIAnswerer(client).answer(question.text, chunks)

    print(f"\nQuestion: {question.text}\nFinanceBench: {question.answer}\nAnswer: {answer.text}")
    assert answer.invalid_citations == 0
    cited = {(c.chunk.document.name, c.chunk.page) for c in answer.citations}
    assert cited & {(question.document.name, page) for page in question.evidence_pages}
    judge = OpenAIJudge(client)
    correctness = judge.correctness(question.text, question.answer, answer.text)
    faithfulness = judge.faithfulness(answer)
    print(f"Judge: {correctness}\n       {faithfulness}")
    assert (correctness.label, faithfulness.label) == ("correct", "supported")
