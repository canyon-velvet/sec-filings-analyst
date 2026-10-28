"""Eval runners: every Question in a Split through an Experiment's Searcher (and, for answer runs,
an Answerer and the Judge) and scoring, saved as a run."""

import json
import os
import secrets
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from types import ModuleType

from sec_filings_analyst import answerer as answering
from sec_filings_analyst import judge as judging
from sec_filings_analyst.answer_scoring import Answered, AnswerMetrics, numeric_match, score_answers
from sec_filings_analyst.answerer import Answer, Answerer
from sec_filings_analyst.chunking import CHUNK_TOKENS
from sec_filings_analyst.experiments import Experiment
from sec_filings_analyst.financebench import Question
from sec_filings_analyst.judge import UNJUDGED, Judge, Verdict
from sec_filings_analyst.retriever import Filter, SearchResult
from sec_filings_analyst.scoring import Metrics, Page, Retrieval, score

FETCH_K = 50  # Chunks per Question: several can share a Page, and scoring needs 10 unique Pages
TOP_PAGES = 5  # retrieved Pages kept per Question, for failure analysis
ANSWER_CHUNKS = 10  # Chunks the Answerer gets per Question
EXCERPT_OVERHEAD = 40  # tokens per Chunk in the prompt beyond its text: marker, header, newlines
_SUPPORTED = {"supported": True, "not supported": False}  # UNJUDGED: None


def run_eval(
    experiment: Experiment, split: str, questions: list[Question], provenance: dict, eval_dir: Path
) -> None:
    """Saves eval_dir/runs/<split>/<experiment name>.json, with provenance (commit, corpus)
    recorded as given, and regenerates eval_dir/RESULTS.md from every saved run. Raises
    FileExistsError, before any search, if the experiment was already run on this Split, and
    ValueError for an experiment name that isn't a plain file name or a corpus whose Contextual
    headers aren't the ones the experiment expects."""
    name = experiment.name
    path = _new_run_path(experiment, eval_dir / "runs" / split, provenance)
    retrievals = {}
    for question in questions:
        results = _search(experiment, question, FETCH_K)
        ranked = [Page(r.chunk.document.name, r.chunk.page) for r in results]
        retrievals[question.id] = Retrieval(question.question_type, ranked, _evidence(question))
    scores = score(retrievals)
    run = {
        "experiment": name,
        "split": split,
        "config": experiment.settings | {"fetch_k": FETCH_K},
        "commit": provenance["commit"],
        "corpus": provenance["corpus"],
        # Such Questions are scored @10 on fewer than 10 Pages, which can lower the @10 metrics
        "fewer_than_10_pages": sum(len(set(r.ranked)) < 10 for r in retrievals.values()),
        "overall": asdict(scores.overall),
        "by_type": {t: asdict(m) for t, m in scores.by_type.items()},
        "questions": {
            qid: {
                "question_type": r.question_type,
                "first_evidence_rank": scores.per_question[qid].first_evidence_rank,
                "evidence_pages": sorted(_pair(p) for p in r.evidence),
                "top_pages": [_pair(p) for p in list(dict.fromkeys(r.ranked))[:TOP_PAGES]],
            }
            for qid, r in retrievals.items()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    _write(path, json.dumps(run, indent=2) + "\n", replace=False)
    _write_results(eval_dir)


def run_answer_eval(
    experiment: Experiment,
    split: str,
    questions: list[Question],
    provenance: dict,
    answerer: Answerer,
    judge: Judge,
    confirm: Callable[[str], bool],
    eval_dir: Path,
) -> None:
    """Answers each Question from the Experiment's top ANSWER_CHUNKS Chunks and has the Judge
    grade it. Saves eval_dir/answer_runs/<split>/<experiment name>.json with the verdicts but no
    Answer text or Judge reasons, which can restate FinanceBench's (CC-BY-NC), and those beside it
    in a gitignored .local.jsonl; regenerates eval_dir/RESULTS.md. Refuses names and corpora as
    run_eval does, then asks confirm() about the cost ceiling, all before any call; a no stops
    it."""
    path = _new_run_path(experiment, eval_dir / "answer_runs" / split, provenance)
    if not confirm(_cost_ceiling(questions, answerer.model, judge.model)):
        return
    answered, local = {}, []
    for question in questions:
        chunks = [r.chunk for r in _search(experiment, question, ANSWER_CHUNKS)]
        answer = answerer.answer(question.text, chunks)
        # Unique Pages in the order first cited: two cited Chunks can share a Page
        cited = list(
            dict.fromkeys(Page(c.chunk.document.name, c.chunk.page) for c in answer.citations)
        )
        invalid = answer.invalid_citations
        matched = numeric_match(question.answer, answer.text)
        correctness, faithfulness = _judge(judge, question, answer)
        verdicts = [v.label for v in (correctness, faithfulness) if v]
        answered[question.id] = Answered(
            question_type=question.question_type,
            cited=cited,
            invalid_citations=invalid,
            evidence=_evidence(question),
            numeric_match=matched,
            correctness=correctness.label,
            supported=None if not faithfulness else _SUPPORTED.get(faithfulness.label),
            unjudged=verdicts.count(UNJUDGED),
        )
        local.append(
            {
                "id": question.id,
                "answer": answer.text,
                "correctness_reason": correctness.reason,
                "faithfulness_reason": faithfulness and faithfulness.reason,
            }
        )
    scores = score_answers(answered)
    run = {
        "experiment": experiment.name,
        "split": split,
        "config": experiment.settings
        | {
            "answer_model": answerer.model,
            "answer_chunks": ANSWER_CHUNKS,
            "judge_model": judge.model,
        },
        "commit": provenance["commit"],
        "corpus": provenance["corpus"],
        "overall": asdict(scores.overall),
        "by_type": {t: asdict(m) for t, m in scores.by_type.items()},
        "questions": {
            qid: {
                "question_type": a.question_type,
                "evidence_pages": sorted(_pair(p) for p in a.evidence),
                "cited_pages": [_pair(p) for p in a.cited],
                "invalid_citations": a.invalid_citations,
                "citation_hit": scores.citation_hits[qid],
                "numeric_match": a.numeric_match,
                "correctness": a.correctness,
                "supported": a.supported,
                "unjudged": a.unjudged,
            }
            for qid, a in answered.items()
        },
    }
    lines = [json.dumps(row) + "\n" for row in local]
    path.parent.mkdir(parents=True, exist_ok=True)
    # The text first: a run file never exists without its Answers and reasons
    _write(path.with_suffix(".local.jsonl"), "".join(lines), replace=True)
    _write(path, json.dumps(run, indent=2) + "\n", replace=False)
    _write_results(eval_dir)


def _judge(judge: Judge, question: Question, answer: Answer) -> tuple[Verdict, Verdict | None]:
    """The correctness and faithfulness verdicts; no faithfulness one for a refusal or an empty
    Answer, which claim nothing. Without the Judge: an empty Answer is incorrect, and one citing
    nothing can't be supported."""
    if not answer.text.strip():
        return Verdict("incorrect", "The Answer is empty."), None
    correctness = judge.correctness(question.text, question.answer, answer.text)
    if correctness.label == "refused":
        return correctness, None
    if not answer.citations:
        return correctness, Verdict("not supported", "The Answer cites no excerpt.")
    return correctness, judge.faithfulness(answer)


def _cost_ceiling(questions: list[Question], answer_model: str, judge_model: str) -> str:
    """At most what answering and judging cost, known before retrieval: each Chunk at its
    CHUNK_TOKENS cap, instructions and FinanceBench text at one token per character, each Answer
    and verdict at its output cap (reasoning is off, so there are no hidden reasoning tokens)."""
    n, excerpts = len(questions), ANSWER_CHUNKS * (CHUNK_TOKENS + EXCERPT_OVERHEAD)
    answer_in = sum(len(answering.INSTRUCTIONS) + len(q.text) + excerpts for q in questions)
    answer_out = n * answering.MAX_ANSWER_TOKENS
    graded = answering.MAX_ANSWER_TOKENS  # the Answer, in both of the Judge's prompts
    judge_in = sum(
        len(judging.CORRECTNESS_INSTRUCTIONS) + len(q.text) + len(q.answer) + graded
        for q in questions
    )
    judge_in += n * (len(judging.FAITHFULNESS_INSTRUCTIONS) + graded + excerpts)
    judge_out = n * 2 * judging.MAX_JUDGE_TOKENS
    answer_cost = _cost(answer_in, answer_out, answering)
    judge_cost = _cost(judge_in, judge_out, judging)
    return (
        f"Answer {n} Questions with {answer_model} (at most {answer_in:,} input and"
        f" {answer_out:,} output tokens, ${answer_cost:.2f}) and judge them with {judge_model}"
        f" (at most {judge_in:,} input and {judge_out:,} output tokens, ${judge_cost:.2f}):"
        f" ${answer_cost + judge_cost:.2f}"
    )


def _cost(tokens_in: int, tokens_out: int, prices: ModuleType) -> float:
    """USD at a model module's INPUT_ and OUTPUT_PRICE_PER_MILLION."""
    return (
        tokens_in * prices.INPUT_PRICE_PER_MILLION + tokens_out * prices.OUTPUT_PRICE_PER_MILLION
    ) / 1e6


def _new_run_path(experiment: Experiment, folder: Path, provenance: dict) -> Path:
    """Where the Experiment's new run goes. Raises FileExistsError if it was already run, and
    ValueError for a name that isn't a plain file name or a corpus whose Contextual headers
    aren't the ones the Experiment expects."""
    name = experiment.name
    if Path(name).name != name:
        raise ValueError(f"experiment {name!r} must be a plain name, without folders")
    path = folder / f"{name}.json"
    if path.exists():
        raise FileExistsError(f"{path} exists; name the new run differently")
    expected = experiment.settings.get("header_format")  # None: bare Chunks
    corpus = provenance["corpus"].get("header_format")
    if corpus != expected:
        expects, has = (f"headers {f!r}" if f else "no headers" for f in (expected, corpus))
        raise ValueError(f"{name} expects Chunks with {expects}, but the corpus has {has}")
    return path


def _search(experiment: Experiment, question: Question, k: int) -> list[SearchResult]:
    filter = None
    if experiment.oracle_filter:
        document = question.document
        filter = Filter(document.company, document.doc_type, document.fiscal_year)
    return experiment.searcher.search(question.text, k=k, filter=filter)


def _evidence(question: Question) -> set[Page]:
    return {Page(question.document.name, n) for n in question.evidence_pages}


def _write_results(eval_dir: Path) -> None:
    table = _results_table(sorted((eval_dir / "runs").rglob("*.json")))
    answer_runs = sorted((eval_dir / "answer_runs").rglob("*.json"))
    if answer_runs:
        table += "\n" + _answer_table(answer_runs)
    _write(eval_dir / "RESULTS.md", table, replace=True)


def _write(path: Path, text: str, replace: bool) -> None:
    """Writes text as UTF-8 to a temporary file beside path, then puts it in place in one step,
    so a crashed or killed run never leaves half a file (there's no fsync, so a power loss
    still could). Unless replace, an existing path raises FileExistsError: os.link never
    overwrites."""
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")  # unique, unlike a PID
    try:
        with tmp.open("x", encoding="utf-8") as file:  # created with the umask's mode, like path
            file.write(text)
        if replace:
            tmp.replace(path)
        else:
            os.link(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)  # already gone after replace


def _pair(page: Page) -> list:
    return [page.document_name, page.number]


def _results_table(run_files: list[Path]) -> str:
    runs = [json.loads(f.read_text(encoding="utf-8")) for f in run_files]
    types = sorted({t for run in runs for t in run["by_type"]})
    lines = [
        "# Retrieval results",
        "",
        "Generated by `make eval` from `eval/runs/`; don't edit by hand.",
        "",
        "An Experiment whose settings set an oracle filter searches only each Question's company,",
        "Doc type and Fiscal year, which no user knows: an upper bound, not a result.",
        "",
        _row(["Experiment", "Split", "Hit@1", "Hit@5", "Hit@10", "Recall@10", "MRR@10", "n"]),
        _separator(8),
    ]
    for run in runs:
        m = Metrics(**run["overall"])
        cells = [m.hit_at_1, m.hit_at_5, m.hit_at_10, m.recall_at_10, m.mrr_at_10]
        lines.append(_row([run["experiment"], run["split"], *map(_fmt, cells), str(m.n)]))
    lines += ["", "## Hit@5 by question type", "", _row(["Experiment", "Split", *types])]
    lines.append(_separator(len(types) + 2))
    for run in runs:
        by_type = run["by_type"]
        hits = [_fmt(by_type[t]["hit_at_5"]) if t in by_type else "–" for t in types]
        lines.append(_row([run["experiment"], run["split"], *hits]))
    return "\n".join(lines) + "\n"


def _answer_table(run_files: list[Path]) -> str:
    runs = [json.loads(f.read_text(encoding="utf-8")) for f in run_files]
    columns = ["Experiment", "Split", "Answer model", "Citation hit", "Numeric check"]
    columns += ["Invalid citations", "n"]
    lines = [
        "# Answer results",
        "",
        "Generated by `make answer-eval` from `eval/answer_runs/`. Citation hit: the Answer cites",
        "at least one Evidence page. Numeric check, of the Questions whose FinanceBench answer is",
        "a number: the Answer states it within 1%. Invalid citations: markers matching no Chunk",
        "the Answer was given.",
        "",
        _row(columns),
        _separator(len(columns)),
    ]
    for run in runs:
        m = AnswerMetrics(**run["overall"])
        model = run["config"]["answer_model"]
        numeric = (
            "–" if m.numeric_accuracy is None else f"{_fmt(m.numeric_accuracy)} of {m.numeric_n}"
        )
        cells = [model, _fmt(m.citation_hit_rate), numeric]
        cells += [str(m.invalid_citations), str(m.n)]
        lines.append(_row([run["experiment"], run["split"], *cells]))
    return "\n".join(lines) + "\n"


def _row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _separator(columns: int) -> str:
    return "|" + "---|" * columns


def _fmt(value: float) -> str:
    return f"{value:.2f}"


if __name__ == "__main__":
    import subprocess
    import sys

    import openai
    import psycopg

    from sec_filings_analyst.answerer import OpenAIAnswerer
    from sec_filings_analyst.embedder import OpenAIEmbedder
    from sec_filings_analyst.experiments import build_experiment
    from sec_filings_analyst.financebench import load_questions
    from sec_filings_analyst.ingest import describe_corpus
    from sec_filings_analyst.judge import OpenAIJudge

    split_name, name, *mode = sys.argv[1:]  # e.g. dev dense-headers, then "answers" for answers
    split_file = Path("eval/splits/financebench_v1.json")
    ids = set(json.loads(split_file.read_text())[split_name])
    all_questions = load_questions(Path("data/financebench/financebench_merged.jsonl"))
    questions = [q for q in all_questions if q.id in ids]

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout

    # -dirty: uncommitted changes (code, pins, Split), apart from the eval outputs runs write
    outputs = [":!eval/runs", ":!eval/answer_runs", ":!eval/RESULTS.md"]
    changes = git("status", "--porcelain", "--", ".", *outputs)
    commit = git("rev-parse", "HEAD").strip() + ("-dirty" if changes else "")
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn:
        # First: it refuses a database without corpus settings, before a Searcher queries it
        provenance = {"commit": commit, "corpus": describe_corpus(conn)}
        client = openai.OpenAI()
        experiment = build_experiment(name, conn, OpenAIEmbedder(client))
        split = f"{split_file.stem}/{split_name}"
        if mode == ["answers"]:

            def ask(summary: str) -> bool:
                return input(f"{summary}. Go ahead? [y/N] ").strip().lower() == "y"

            answerer, judge = OpenAIAnswerer(client), OpenAIJudge(client)
            run_answer_eval(
                experiment, split, questions, provenance, answerer, judge, ask, Path("eval")
            )
        else:
            run_eval(experiment, split, questions, provenance, Path("eval"))
