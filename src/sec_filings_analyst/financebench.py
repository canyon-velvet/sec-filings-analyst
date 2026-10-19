"""FinanceBench open sample: its 150 Questions and the 84 Documents they ask about."""

import http.client
import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sec_filings_analyst.documents import Document

# Pinned revisions, so every run downloads the same inputs.
QUESTIONS_URL = (
    "https://huggingface.co/datasets/PatronusAI/financebench/resolve/"
    "e04404e3a97f69f79c14d42f24981a1c9c3bcd18/financebench_merged.jsonl"
)
PDF_URL = (
    "https://github.com/patronus-ai/financebench/raw/"
    "cc39aeb4afdf33909ee1412188bf89035950c2eb/pdfs/{name}.pdf"
)
DOC_TYPES = {"10k": "10-K", "10q": "10-Q", "8k": "8-K", "Earnings": "Earnings"}


@dataclass(frozen=True)
class Question:
    id: str  # financebench_id
    question_type: str  # domain-relevant, metrics-generated, novel-generated
    document: Document
    text: str
    answer: str
    evidence_pages: frozenset[int]  # Page numbers, 1-based like our Pages


def load_questions(jsonl: Path) -> list[Question]:
    """Questions in file order, with Doc types normalized (10k → 10-K) and Evidence pages
    shifted to 1-based Pages (FinanceBench numbers pages from 0)."""
    with jsonl.open(encoding="utf-8") as rows:
        return [_question(json.loads(row)) for row in rows]


def _question(row: dict) -> Question:
    document = Document(
        row["doc_name"], row["company"], DOC_TYPES[row["doc_type"]], row["doc_period"]
    )
    return Question(
        id=row["financebench_id"],
        question_type=row["question_type"],
        document=document,
        text=row["question"],
        answer=row["answer"],
        evidence_pages=frozenset(e["evidence_page_num"] + 1 for e in row["evidence"]),
    )


def download(data_dir: Path, fetch: Callable[[str], bytes]) -> None:
    """Saves the Questions file and each Document's PDF under data_dir, skipping files already
    there. Raises RuntimeError naming the Document whose PDF can't be downloaded."""
    pdf_dir = data_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    questions_file = data_dir / "financebench_merged.jsonl"
    if not questions_file.exists():
        _save(questions_file, fetch(QUESTIONS_URL))
    documents = {q.document for q in load_questions(questions_file)}
    for document in sorted(documents, key=lambda d: d.name):
        pdf = pdf_dir / f"{document.name}.pdf"
        if not pdf.exists():
            print(f"Downloading {document.name}")
            _save(pdf, _fetch_pdf(document, fetch))


def _fetch_pdf(document: Document, fetch: Callable[[str], bytes]) -> bytes:
    try:
        content = fetch(PDF_URL.format(name=document.name))
    except (OSError, http.client.HTTPException) as error:  # e.g. 404, timeout, dropped connection
        raise RuntimeError(f"{document.name}: download failed: {error}") from error
    if not content.startswith(b"%PDF-"):  # e.g. an HTML error page served with status 200
        raise RuntimeError(f"{document.name}: download is not a PDF")
    return content


def _save(path: Path, content: bytes) -> None:
    """Writes then renames, so an interrupted run never leaves a partial file that looks done."""
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(content)
    partial.replace(path)


def fetch_url(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


if __name__ == "__main__":
    download(Path("data/financebench"), fetch_url)
