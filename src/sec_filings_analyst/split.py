"""Split: Questions partitioned once into dev (tuning) and test (reporting), stratified by type."""

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from sec_filings_analyst.financebench import Question, load_questions

SEED = 2026  # fixed, so financebench_v1 can be re-derived from the pinned Questions


@dataclass(frozen=True)
class Split:
    dev: list[str]  # Question ids, sorted
    test: list[str]


def make_split(questions: list[Question], dev_size: int, seed: int) -> Split:
    """Each question type gets its share of dev_size (largest remainder; ties go to the type
    that sorts first), drawn at random with the seed."""
    by_type: dict[str, list[str]] = {}
    for q in sorted(questions, key=lambda q: (q.question_type, q.id)):
        by_type.setdefault(q.question_type, []).append(q.id)
    total = len(questions)
    quotas = {t: dev_size * len(ids) // total for t, ids in by_type.items()}
    by_remainder = sorted(by_type, key=lambda t: -(dev_size * len(by_type[t]) % total))
    for t in by_remainder[: dev_size - sum(quotas.values())]:
        quotas[t] += 1
    rng = random.Random(seed)
    dev = {qid for t, ids in by_type.items() for qid in rng.sample(ids, quotas[t])}
    return Split(sorted(dev), sorted(q.id for q in questions if q.id not in dev))


def write_split(split: Split, path: Path) -> None:
    """Writes the Split once; raises FileExistsError rather than replace a committed version."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as file:
        json.dump(asdict(split), file, indent=2)
        file.write("\n")


if __name__ == "__main__":
    questions = load_questions(Path("data/financebench/financebench_merged.jsonl"))
    split = make_split(questions, dev_size=50, seed=SEED)
    write_split(split, Path("eval/splits/financebench_v1.json"))
