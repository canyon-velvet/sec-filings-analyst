import json

from fakes.openai_client import FakeOpenAIClient

from sec_filings_analyst.answerer import cite
from sec_filings_analyst.documents import Chunk, Document
from sec_filings_analyst.judge import OpenAIJudge, Verdict

ACME = Document("ACME_2023_10K", "ACME", "10-K", 2023)
CHUNKS = [
    Chunk(ACME, 12, 0, "Revenue was 40 million dollars.", 6),
    Chunk(ACME, 40, 0, "Capital expenditures were 7 million dollars.", 6),
]


def reply(verdict: str, reason: str) -> str:
    return json.dumps({"reason": reason, "verdict": verdict})


def test_grades_correctness_against_financebench_s_answer_with_the_pinned_model():
    client = FakeOpenAIClient(reply("refused", "It says the excerpts don't give capex."))

    verdict = OpenAIJudge(client).correctness(
        "What was ACME's FY2023 capex?", "$7 million", "I can't find capex in the documents."
    )

    assert verdict == Verdict("refused", "It says the excerpts don't give capex.")
    (request,) = client.chat_requests
    assert request["model"] == "gpt-5.4-2026-03-05"
    assert (request["temperature"], request["reasoning_effort"]) == (0, "none")
    schema = request["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["verdict"]["enum"] == ["correct", "incorrect", "refused"]
    prompt = request["messages"][-1]["content"]
    assert all(s in prompt for s in ["ACME's FY2023 capex", "$7 million", "I can't find capex"])


def test_checks_faithfulness_against_only_the_chunks_the_answer_cites_under_their_markers():
    client = FakeOpenAIClient(reply("not supported", "Revenue isn't in excerpt [2]."))
    answer = cite("Revenue was $40M and capex $7M [2].", CHUNKS)

    verdict = OpenAIJudge(client).faithfulness(answer)

    assert verdict == Verdict("not supported", "Revenue isn't in excerpt [2].")
    (request,) = client.chat_requests
    assert request["model"] == "gpt-5.4-2026-03-05"
    schema = request["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["verdict"]["enum"] == ["supported", "not supported"]
    prompt = request["messages"][-1]["content"]
    assert "Revenue was $40M and capex $7M [2]." in prompt
    assert "[2] ACME 10-K FY2023, page 40\nCapital expenditures were 7 million dollars." in prompt
    assert "Revenue was 40 million dollars." not in prompt  # [1] wasn't cited


def test_a_reply_without_a_usable_verdict_is_unjudged_rather_than_a_crash_mid_run():
    cut_off = FakeOpenAIClient('{"reason": "The answer gives', finish_reason="length")
    refused = FakeOpenAIClient(None)

    for client in cut_off, refused:
        verdict = OpenAIJudge(client).correctness("Q?", "$7 million", "Capex was $7M [2].")
        assert verdict.label == "unjudged"
    assert "length" in OpenAIJudge(cut_off).faithfulness(cite("Capex was $7M [2].", CHUNKS)).reason
