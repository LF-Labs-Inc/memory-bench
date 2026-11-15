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

Since 2026-11-14 memory-bench publishes no recall figure in any form, raw or leak-adjusted: not in the README, its
chart, `report.md` or the reference comparisons. Systems are compared by answered right (cases passed over cases
scored), with every leak rate and the pass rate of every area beside it. The leak-adjusted figure this audit
introduced ("found without leaking") was dropped too: it catches a leak only inside the recall cases, where the leak
penalty barely moves it, while the leak probes themselves show the leaks; it covers about one case in ten (23 of the
273, 107 of the 1,040); it inherits the unequal intake in finding 2; and answered right already counts a case whose
needed facts were missing. The findings below keep what was learned about the scorer and the adapters, with no figure
comparing the systems on recall.

## Findings

### 1. Recall ignored leaks

`harness/score.py:749-757` sets a case's `recall` from the needed facts before the leak check; a forbidden hit then
zeroes the case's score and pass (`harness/score.py:815-816`) but leaves `recall` as it was. `harness/report.py`
averaged `r["recall"]` (line 140 before this change). So a context that carried the needed fact together with
forbidden content counted as full recall. The fix stays: `summary.json` also records a leak-adjusted recall, which
counts a case that leaked as not found. Pass and fail were never affected, so answered right, the area pass rates and
the leak rates are unchanged by it.

### 2. Unequal intake of other people's words

`harness/adapters/mem0.py:47-55` (`turn_message`) sends every turn by someone other than the user or the assistant to
Mem0 as a `role: user` message, `"Name: text"`. `harness/adapters/_dawnmere_bridge.py:484-492` (the default, product
mode) writes those turns into the Claude Code transcript as `Read` or `WebFetch` tool results, which the engine by
design never saves as the user's words (`harness/adapters/COMPETITORS.md`, the Dawnmere table). So Mem0 extracts
memories directly from texts, emails, meetings and web pages; Dawnmere learns from them only through what the user or
the assistant said about them. That affects every comparison of the two rows, including the area pass rates where
Mem0 passes more cases (retrieval, attribution, multi-hop), and its size is not known until a matched-intake run is
made (below).

`summary.json` keeps, as a machine record, the share of needed facts found split by who stated each fact (`stated_by`
in `world/truth.jsonl`: the user or the assistant, or anyone else). It is computed from a dev run's `cases.jsonl`; a
test run saves no per-case missing facts, so it has no such split.

### 3. Small n

The recall cases (`context_recall`) are 23 of the 273 cases of the earlier test cut, 29 of the 244 on dev and 107 of
the 1,040 of the whole test half. A recall figure over them carries a wide interval and, as finding 2 says, unequal
input; it is one reason no recall figure is published.

### 4. Lenient match on a short value (minor)

Dev case e-robustness-0045 ("where do i usually do groceries", gold "Basalt Market.") is credited to Mem0 from a
memory that Jo was at the Basalt Market parking lot loading groceries after a car backed into hers. The value is found
by its tokens; the memory is about an accident, not where she usually shops. One case; the scorer is not changed here.

## Fixed now

- `harness/report.py` adds to `summary.json` `context`: `recall_n`, `recall_ci95`, `recall_without_leak_mean` (a
  case's recall, or 0 when it had a forbidden hit), `recall_without_leak_ci95`, and `recall_by_fact_origin` (split by
  who stated each needed fact). Existing keys and values are unchanged. These are machine records; since 2026-11-14
  `report.md` prints none of them, nor any recall mean or mean-score column. Tests in `tests/test_report.py`.
- `tools/fairness_recall.py` recomputes these from the saved runs with no model calls and prints them as tables. It is
  a maintainers' tool for checking the records, not a published table.
- `README.md`, held-out section: one sentence on intake with a link here. It states no recall figure (since
  2026-11-14).

## Not done

- **A matched-intake run.** Either Mem0 given only the user's and the assistant's turns (as Dawnmere gets them), or
  Dawnmere given other people's words through a saved intake path, as Mem0 gets them. Either needs a full replay with
  model calls and was not run, so the size of the intake effect on the test half is unknown. The existing equal-access
  track (`results/reference/dawnmere-equal-access`) is not that run: it reproduces Jarvis's intake (saved contacts
  only, capped per run and per day) on engine 0.1.3, on the same 244 dev cases.
- **The short-value match** in finding 4 is left as it is.
