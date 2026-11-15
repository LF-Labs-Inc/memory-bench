# Fairness audit, 2026-11-12

Three reviewers read, independently, how the Dawnmere and Mem0 rows are produced and scored: the scorer
(`harness/score.py`), the aggregation (`harness/report.py`), the two adapters, and the saved reference runs. Every
finding below was checked on the dev per-case records. The test half was looked at only through the aggregates already
published in `results/reference/*/2026111*-test-s0/summary.json`; no test per-case data was opened.

Runs used:

- dev, Dawnmere: `results/reference/dawnmere/20261110T074032Z-dev-s0` (244 cases)
- dev, Mem0: `results/reference/mem0/20261015T183924Z-dev-s0-rescored-public`, restricted to the same 244 case ids
- test: `results/reference/dawnmere/20261110T161902Z-test-s0` and `results/reference/mem0/20261110T184704Z-test-s0`
  (273 cases each)

"Found without leaking" below is over the `context_recall` cases: the share of each case's needed facts that the
injected context carried (by tokens, then by the judge for those the tokens missed), counted as 0 for a case whose
context carried anything forbidden, averaged over cases.

## Findings

### 1. Recall ignored leaks

`harness/score.py:749-757` sets a case's `recall` from the needed facts before the leak check; a forbidden hit then
zeroes the case's score and pass (`harness/score.py:815-816`) but leaves `recall` as it was. `harness/report.py`
averaged `r["recall"]` (line 140 before this change). So a context that carried the needed fact together with
forbidden content counted as full recall. The figure now reported counts a case that leaked as not found.

On test (n=23 recall cases), found without leaking: Mem0 17/23 (73.9%), Dawnmere 15/23 (65.2%). On dev (n=29):
Mem0 75.9% (four recall cases leaked: d-forget-0115, d-forget-0116, d-poisoning-0093, d-poisoning-0126), Dawnmere
70.7% (one: d-forget-0115).

### 2. Unequal intake of other people's words

`harness/adapters/mem0.py:47-55` (`turn_message`) sends every turn by someone other than the user or the assistant to
Mem0 as a `role: user` message, `"Name: text"`. `harness/adapters/_dawnmere_bridge.py:484-492` (the default, product
mode) writes those turns into the Claude Code transcript as `Read` or `WebFetch` tool results, which the engine by
design never saves as the user's words (`harness/adapters/COMPETITORS.md`, the Dawnmere table). So Mem0 extracts
memories directly from texts, emails, meetings and web pages; Dawnmere learns from them only through what the user or
the assistant said about them.

On the 244 dev cases, the 29 recall cases need 40 facts. Split by who stated each fact (`stated_by` in
`world/truth.jsonl`), counting a fact as found only when its case's context carried nothing forbidden:

| needed facts stated by | Dawnmere found without leaking | Mem0 found without leaking |
|---|---|---|
| the user or the assistant (31) | 27 (87.1%, 95% interval 71 to 95%) | 26 (83.9%, 67 to 93%) |
| other people (9) | 2 (22.2%, 6 to 55%) | 6 (66.7%, 35 to 88%) |

So on dev the gap between the two is in the facts other people stated; on the user's and the assistant's facts
Dawnmere is level with Mem0. The split is computed from the two runs' `cases.jsonl` on the 244 shared ids: a fact
counts when it is not in the case's `detail.missing_facts` and the case has no leak.

The facts' `stated_by` is read from the current `world/truth.jsonl`. The Mem0 dev run was scored on an earlier data
fingerprint than the Dawnmere one; on all 29 recall cases the two records list the same needed facts.

### 3. Small n

The figure is over the 23 `context_recall` cases of the test half, not over its 273 cases (29 of the 244 on dev).
The 95% Wilson intervals on test are 54 to 87% for Mem0's 73.9% and 45 to 81% for Dawnmere's 65.2%. Counting cases
fully found without leaking, 17/23 against 15/23 gives a two-sided Fisher exact p of about 0.75. The origin split on
dev is smaller still (9 facts by other people).

### 4. Lenient match on a short value (minor)

Dev case e-robustness-0045 ("where do i usually do groceries", gold "Basalt Market.") is credited to Mem0 from a
memory that Jo was at the Basalt Market parking lot loading groceries after a car backed into hers. The value is found
by its tokens; the memory is about an accident, not where she usually shops. One case; the scorer is not changed here.

## Fixed now

- `harness/report.py` adds to `summary.json` `context` (and to `report.md`): `recall_n`, `recall_ci95`,
  `recall_without_leak_mean` (a case's recall, or 0 when it had a forbidden hit), `recall_without_leak_ci95`, and
  `recall_by_fact_origin` (split by who stated each needed fact: the user or the assistant, or anyone else, with
  intervals). Existing keys and values are unchanged. Intervals are Wilson 95% intervals that take a case as one trial,
  approximate when a case's recall is a fraction. Tests in `tests/test_report.py`.
- `tools/fairness_recall.py` recomputes these from the saved runs with no model calls: every dev run from its
  `cases.jsonl`, on all its cases and on the 244 shared ids; the two test runs from `summary.json` only. For test,
  recall found without leaking is `by_scoring.context_recall.mean_score`. That equals the new figure when every
  `context_recall` case has needed facts and none is an abstain case below L3 (whose near-miss rule can also zero the
  score); on every dev run here the two figures are identical. There is no origin
  split for test: it needs each case's missing facts, which a test run does not save.
- `README.md`, held-out section: n=23, the intervals and the leak-adjusted figures, and one sentence on intake with a
  link here. (Since 2026-11-14 the README and this audit state only the leak-adjusted figure, not the raw one.)

## Not done

- **A matched-intake run.** Either Mem0 given only the user's and the assistant's turns (as Dawnmere gets them), or
  Dawnmere given other people's words through a saved intake path, as Mem0 gets them. Either needs a full replay with
  model calls and was not run, so the size of the intake effect on the test half is unknown. The existing equal-access
  track (`results/reference/dawnmere-equal-access`) is not that run: it reproduces Jarvis's intake (saved contacts
  only, capped per run and per day) on engine 0.1.3, on the same 244 dev cases.
- **The short-value match** in finding 4 is left as it is.
- **More recall cases.** With 23 test recall cases, differences under about 20 points are within noise; only more
  cases or more runs change that. The whole test half (1,040 cases, 2026-11-12) has 107.
