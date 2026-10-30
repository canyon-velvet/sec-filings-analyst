# Week 2 results: the test Split

Date: 2026-10-30 · Ticket: #38 · Runs: `eval/runs/financebench_v1/test/dense-headers.json`,
`eval/answer_runs/financebench_v1/test/dense-headers.json` (both at commit `de15292`)

`dense-headers` (dense search over Chunks embedded with their Contextual header, top 10 Chunks
to the Answerer) was picked on dev alone, then run once on the 100 test Questions, for
retrieval and for Answers. Nothing was changed after seeing them. Every week-2 technique's
dev numbers are in `eval/RESULTS.md`.

## Dev and test

| Split | Hit@5 | Hit@10 | MRR@10 | Accuracy | Refused | Numeric check | Faithful | Citation hit | n |
|---|---|---|---|---|---|---|---|---|---|
| dev | 0.54 | 0.64 | 0.31 | 0.60 | 0.14 | 0.65 of 17 | 0.63 | 0.62 | 50 |
| test | 0.54 | 0.73 | 0.35 | 0.60 | 0.15 | 0.63 of 35 | 0.58 | 0.63 | 100 |

- **Test matches dev**, so the choices made on dev show no sign of overfitting it.
  Both Splits draw on the same 84 Documents, though: test checks new Questions, not new
  companies.
- **The Judge** agrees with the numeric check on 26 of the 27 numeric Answers it graded correct
  or incorrect. In the other one (`financebench_id_05718`), it accepted a figure about 3% off
  FinanceBench's rounded one as rounding; the check allows 1%. On dev it agreed with 18 of 20
  hand grades (docs/adr/0003).
- **Faithfulness is lower on test:** 21 of the 60 correct Answers add a claim the Chunks they
  cite don't state (7 of 30 on dev).

## By question type (test)

| Question type | Hit@5 | Accuracy | Refused | Incorrect | Faithful | n |
|---|---|---|---|---|---|---|
| domain-relevant | 0.42 | 0.64 | 4 | 8 | 0.41 | 33 |
| metrics-generated | 0.48 | 0.64 | 8 | 4 | 0.64 | 33 |
| novel-generated | 0.71 | 0.53 | 3 | 13 | 0.68 | 34 |

Of the 40 Answers that aren't correct, about half fail in reading, not search: 18 cite an
Evidence page, and 22 had one in the top 10 Pages (an upper bound, since the Answerer gets the
top 10 Chunks, which can cover fewer Pages). The other 18 had no Evidence page in the top 10.

## Where retrieval misses

Of the 46 Questions with no Evidence page in the top 5:

- **40 have the right Document but the wrong Page.** Contextual headers find the Document;
  a 10-K's Pages still look alike.
- **5 rank another Document of the same company first:** another year or quarter, or a 10-K
  in place of an earnings release or the reverse. Three were still answered correctly: two from
  a Document that repeats the figure, one reaching the same conclusion from other years.
- **1 names no company** (`financebench_id_00601`): it asks why a cost ratio fell in a fiscal
  year, and the top 5 Pages come from three companies, only one of them the right one.
  Search alone can't fix that: the company has to come from the user.

## Metrics-generated: one statement found, the other missing

Many of these Questions define a ratio from two statements, such as the cash flow statement
and the balance sheet. 15 of the 33 have Evidence on two or more Pages, and only 4 of those 15
are correct, against 17 of 18 with one Evidence page. 11 of the 12 failures need two or more
Pages:

- **7 of the 8 refusals** need two or more Pages. In the three with an Evidence page in the
  top 10, the Answer gives the figures it found and names the one it is missing: the current
  liabilities for a cash flow ratio (`financebench_id_03856`), the cost of sales for days payable
  (`financebench_id_06247`), the first year of a three-year average (`financebench_id_07966`).
- **One search can't fetch two statements.** The week-3 agent can search once per statement.

## Novel-generated: the right Page, the wrong reading

These have the best retrieval (Hit@5 0.71) and the lowest accuracy (0.53). 10 of the 13
incorrect Answers had an Evidence page in the top 10 Pages, and 12 of the 13 need only one Page:

- **A narrower quantity than asked:** one segment's store count instead of the company's
  (`financebench_id_00460`), and the limit of each of two credit agreements instead of their
  total (`financebench_id_00882`). Both cite the Evidence page.
- **Another Document's figures:** the right yes on whether a margin rose, but with percentages
  from a later Document that reports them for continuing operations only (`financebench_id_01487`).
  The Judge graded the figures (incorrect): a judgement call the rubric leaves open, like the
  two in docs/adr/0003.
- **A list filled from elsewhere:** asked for acquisitions, the Answer names one right company
  and two the Chunks show only as defined terms or a licence deal (`financebench_id_02416`).
  The faithfulness verdict catches it: not supported.
- **A comparison from part of a table:** asked which segment was lowest, the Answer picks from a
  Page that doesn't list them all (`financebench_id_00299`; Evidence at rank 12).

## Domain-relevant

Retrieval is weakest here (Hit@5 0.42), and 7 of the 12 failures had no Evidence page in the
top 10. Faithfulness is lowest too (0.41).

## For week 3

Fixes are tuned on dev; test stays for reporting.

- **Filters from the agent:** oracle filters lift dev Hit@5 to 0.60. They would fix the
  wrong-Document misses, and the agent can ask when a Question names no company.
- **One search per statement** for ratios, then the calculate tool.
- **Answerer instructions:** answer the scope asked (the company, not a segment; the total, not
  each part), and don't name what the Chunks don't show.
