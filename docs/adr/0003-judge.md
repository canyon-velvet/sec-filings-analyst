# 3. Judge: two verdicts per Answer from a pinned gpt-5.4

Date: 2026-10-27 · Status: accepted · Ticket: #36

## Context

FinanceBench's answers are mostly a figure or a short conclusion, worded freely: a bare dollar
figure whose unit is only in the Question, or a yes with a direction. The numeric check (#35) grades only the 17 dev
Questions whose answer is a single number. Every Answer needs a grade, and a grade of its
Citations too: an Answer can be right while claiming more than its excerpts say.

## Decision

- **Two verdicts, each a label and a one-sentence reason:**
  - **Correctness**, from the Question, FinanceBench's answer and the Answer: correct, incorrect
    or refused. A refusal ("can't find it in the documents") is kept apart from incorrect,
    because an honest refusal beats a wrong number.
  - **Faithfulness**, from only the Answer and the Chunks it cites, under the Answer's own
    `[n]` markers and Contextual headers: supported (every claim follows from those excerpts)
    or not supported. No Question and no FinanceBench answer, so it grades support, not truth.
- **Rules, no Judge call:** an empty Answer is incorrect (a failure, not an honest refusal) and
  gets no faithfulness verdict, since it claims nothing. A refusal gets no faithfulness verdict.
  An Answer that isn't a refusal and cites nothing is not supported.
- **Model:** `gpt-5.4-2026-03-05`, pinned. It is the full-size model of the Answerer's family
  (`gpt-5.4-mini-2026-03-17`), so at least as capable, at $2.50 / $15 per million input /
  output tokens, half gpt-5.5's price. Temperature 0 with reasoning off, at most 300 output
  tokens.
- **Reply format:** a strict JSON schema whose `verdict` is an enum of the allowed labels, with
  `reason` first so the label follows from it. A reply without a usable verdict (cut off at the
  cap, or a refusal) becomes **unjudged**, counted per run, not a crash that loses a paid run.
- **Metrics:** accuracy and refusal rate over all Answers; faithfulness over Answers with a
  faithfulness verdict; **Judge–numeric disagreement** over numeric Answers the Judge graded
  correct or incorrect: a refusal can't disagree with the check in a way that says anything
  about the Judge.
- **What is committed:** the labels. The reasons can restate FinanceBench's answer
  (CC-BY-NC), so they stay in the gitignored `.local.jsonl` beside the Answer text.

## Results (dev, 50 Questions, top 10 Chunks)

| Experiment | Hit@5 | Accuracy | Refused | Numeric check | Disagreement | Faithful | Citation hit |
|---|---|---|---|---|---|---|---|
| `dense-headers` | 0.54 | 0.60 | 0.14 | 0.65 of 17 | 0.00 | 0.63 | 0.62 |
| `keyword-bm25-headers` | 0.20 | 0.30 | 0.40 | 0.12 of 17 | 0.00 | 0.47 | 0.22 |

- **Better retrieval, better Answers:** accuracy doubles and refusals fall from 0.40 to 0.14.
  With keyword search the Answerer mostly says it can't find the answer rather than guessing,
  as the instructions ask.
- **The Judge agrees with the numeric check** on every numeric Answer it graded correct or
  incorrect, in both runs. That is one check of the Judge, on figures only; the hand-graded
  sample (#37) checks it on the rest.
- **Faithfulness is strict:** 7 of `dense-headers`' 30 correct Answers are not supported. Each
  adds one claim its excerpts don't state, such as an interpretation of a segment's figures or
  an extra fact. That is the intended reading of "every claim", and the reason to keep the
  Answerer's wording tight.
- `dense-baseline` couldn't be run: the corpus has had Contextual headers since #32, and runs
  refuse a header mismatch. `keyword-bm25-headers` gives the widest retrieval gap on the same
  corpus.

## Alternatives

- **One call for both verdicts:** cheaper, but the faithfulness verdict would see FinanceBench's
  answer and grade truth instead of support.
- **gpt-5.4-mini as the Judge:** about a third of the cost, but the same model grading its own
  Answers is the setup most prone to self-preference.
- **gpt-5.5:** twice the price; revisit if #37 finds the Judge unreliable.
- **Numeric check only:** deterministic, but it covers 17 of 50 dev Questions, and none of the
  explanations.

## Consequences

- An answer run costs at most $1.96 on dev ($0.45 answering, $1.51 judging), shown before any
  call.
- The Judge is checked twice: by the numeric check on every run, and once by the user's hand
  grades (#37), whose agreement rate goes here.
- Unjudged verdicts count as not correct in accuracy; the Unjudged column shows how many.
