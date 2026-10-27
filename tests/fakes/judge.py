from sec_filings_analyst.answerer import Answer
from sec_filings_analyst.judge import Verdict


class FakeJudge:
    """Offline Judge: grades each Answer text with its canned (correctness, faithfulness) labels,
    giving "<label>, by the fake" as the reason, and records the Answer texts it was asked about."""

    model = "fake-judge"

    def __init__(self, verdicts: dict[str, tuple[str, str]]):
        self._verdicts = verdicts
        self.correctness_calls: list[str] = []
        self.faithfulness_calls: list[str] = []

    def correctness(self, question: str, expected: str, answer: str) -> Verdict:
        self.correctness_calls.append(answer)
        label = self._verdicts[answer][0]
        return Verdict(label, f"{label}, by the fake")

    def faithfulness(self, answer: Answer) -> Verdict:
        self.faithfulness_calls.append(answer.text)
        label = self._verdicts[answer.text][1]
        return Verdict(label, f"{label}, by the fake")
