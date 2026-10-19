import json
import random
import re
from difflib import SequenceMatcher
from pathlib import Path

import pytest

from sec_filings_analyst.chunking import parse_pages
from sec_filings_analyst.financebench import load_questions

DATA = Path(__file__).parents[2] / "data" / "financebench"
JSONL = DATA / "financebench_merged.jsonl"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not JSONL.exists(), reason="needs the FinanceBench data: make data"),
]


def similarity(a: str, b: str) -> float:
    """0–1, tolerant of whitespace and case differences between the two text extractions."""
    a, b = (re.sub(r"\s+", " ", s).strip().lower() for s in (a, b))
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def test_full_page_evidence_text_matches_our_parsed_page_at_each_evidence_page():
    with JSONL.open(encoding="utf-8") as rows:
        evidence = [json.loads(row)["evidence"] for row in rows]
    pairs = list(zip(load_questions(JSONL), evidence, strict=True))  # both in file order
    mismatches = []
    for question, items in random.Random(10).sample(pairs, 20):
        pages = parse_pages(DATA / "pdfs" / f"{question.document.name}.pdf")
        for item in items:
            # evidence_pages is a set, so the item's text should match one of its Pages.
            best = max(
                similarity(item["evidence_text_full_page"], pages[number - 1])
                for number in question.evidence_pages
            )
            if best < 0.9:  # every Evidence page matched at ≥ 0.95 when this was settled (#10)
                mismatches.append(f"{question.id} {sorted(question.evidence_pages)}: {best:.2f}")
    assert mismatches == []
