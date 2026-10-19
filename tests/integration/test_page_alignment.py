import json
import random
import re
from difflib import SequenceMatcher
from functools import cache
from pathlib import Path

import pytest

from sec_filings_analyst.chunking import parse_pages
from sec_filings_analyst.financebench import evidence_page

DATA = Path(__file__).parents[2] / "data" / "financebench"
JSONL = DATA / "financebench_merged.jsonl"
SAMPLE_SEED = 10  # any fixed value: the same 20 Questions every run

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not JSONL.exists(), reason="needs the FinanceBench data: make data"),
]


def similarity(a: str, b: str) -> float:
    """0–1, tolerant of whitespace and case differences between the two text extractions."""
    a, b = (re.sub(r"\s+", " ", s).strip().lower() for s in (a, b))
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


@cache  # a Document asked about by two sampled Questions is parsed once
def parsed_pages(doc_name: str) -> list[str]:
    return parse_pages(DATA / "pdfs" / f"{doc_name}.pdf")


def test_full_page_evidence_text_matches_our_parsed_page_at_each_evidence_page():
    with JSONL.open(encoding="utf-8") as rows:
        questions = [json.loads(row) for row in rows]  # FinanceBench's raw rows
    mismatches = []
    for question in random.Random(SAMPLE_SEED).sample(questions, 20):
        pages = parsed_pages(question["doc_name"])
        for evidence in question["evidence"]:
            number = evidence_page(evidence["evidence_page_num"])
            parsed = pages[number - 1] if number <= len(pages) else ""
            score = similarity(evidence["evidence_text_full_page"], parsed)
            if score < 0.9:  # every Evidence page matched at ≥ 0.95 when this was settled (#10)
                mismatches.append(f"{question['financebench_id']} Page {number}: {score:.2f}")
    assert mismatches == []
