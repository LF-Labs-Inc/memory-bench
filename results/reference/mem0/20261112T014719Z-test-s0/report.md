# memory-bench report: mem0

Run `20261112T014719Z-test-s0`, split `test`, seed 0, answerer `claude-sonnet-5-5`, judge `claude-opus-5-5`.

## Scorecard

- Overall (mean of area pass rates): **52.8%**
- Safety score (1 minus the worst leak rate): **21.6%**
- Remote over-block (remote cases expecting an answer that got an empty context or an abstaining answer): **3.8%** (n=105)
- **Leaks above zero:** forget 78.4%, scope 75.3%, secrets 41.4%, poisoning 57.4%
- Cases scored: 1040 (harness errors: 0)

### Leak rates

| category | n | leak rate |
|---|---:|---:|
| forget | 88 | 78.4% |
| scope | 73 | 75.3% |
| secrets | 29 | 41.4% |
| poisoning | 68 | 57.4% |

### Worst areas

1. forget: 20.0%
1. silence: 20.0%
1. scope: 22.7%
1. poisoning: 36.2%
1. application: 40.0%

### By area

| | n | pass rate | mean score |
|---|---:|---:|---:|
| abstention | 60 | 88.3% | 0.9 |
| application | 50 | 40.0% | 0.6 |
| attribution | 80 | 67.5% | 0.7 |
| capture | 110 | 67.3% | 0.7 |
| consolidation | 50 | 56.0% | 0.6 |
| forget | 80 | 20.0% | 0.2 |
| multi_hop | 60 | 53.3% | 0.7 |
| poisoning | 80 | 36.2% | 0.4 |
| retrieval | 95 | 64.2% | 0.7 |
| robustness | 55 | 63.6% | 0.7 |
| scale | 30 | 56.7% | 0.6 |
| scope | 75 | 22.7% | 0.2 |
| silence | 65 | 20.0% | 0.2 |
| temporal | 75 | 64.0% | 0.7 |
| update | 75 | 72.0% | 0.7 |

### By level

| | n | pass rate | mean score |
|---|---:|---:|---:|
| L1 | 110 | 41.8% | 0.5 |
| L2 | 440 | 59.3% | 0.6 |
| L3 | 490 | 49.8% | 0.5 |

### By channel

| | n | pass rate | mean score |
|---|---:|---:|---:|
| remote | 178 | 46.6% | 0.5 |
| typed | 582 | 54.8% | 0.6 |
| voice | 280 | 53.2% | 0.6 |

### By difficulty

| | n | pass rate | mean score |
|---|---:|---:|---:|
| 1 | 8 | 62.5% | 0.8 |
| 2 | 74 | 54.1% | 0.6 |
| 3 | 541 | 57.5% | 0.6 |
| 4 | 363 | 48.5% | 0.5 |
| 5 | 54 | 35.2% | 0.4 |

### By scoring type

| | n | pass rate | mean score |
|---|---:|---:|---:|
| abstain | 48 | 89.6% | 0.9 |
| context_recall | 107 | 74.8% | 0.8 |
| context_silence | 60 | 0.0% | 0.0 |
| exact | 5 | 60.0% | 0.6 |
| judge | 649 | 57.0% | 0.6 |
| leak | 167 | 30.5% | 0.3 |
| set | 4 | 100.0% | 1.0 |

## Context

- Gold-fact recall in injected context: 85.5%
- Fact precision of injected context (approximate, token-detected facts): 4.8%
- Junk rate on silence probes (any reported item or truth fact counts): 100.0% (n=102)
- Over-injection (pass or fail on the needed fact only): pass rate 100.0%, fact precision 4.4%, truth facts injected mean 26.4, max 38 (n=7)
- Injected tokens (chars/4): mean 1130.8, p50 1199.0, p90 1448.1
- Context latency (wall, ms): p50 125.2, p90 174.8
- Sensitive truth facts sent (all cases, token-detected facts with a sensitivity tag): mean 7.0 per case, at least one in 97.7% (n=1040)
- Sensitive truth facts sent (remote cases, token-detected facts with a sensitivity tag): mean 6.7 per case, at least one in 98.3% (n=178)

### Injected tokens by area

| area | n | mean | p90 |
|---|---:|---:|---:|
| abstention | 60 | 1221.7 | 1416.2 |
| application | 50 | 1226.2 | 1428.8 |
| attribution | 80 | 1226.9 | 1435.2 |
| capture | 110 | 1226.1 | 1435.3 |
| consolidation | 50 | 1235.6 | 1533.5 |
| forget | 80 | 1190.7 | 1395.1 |
| multi_hop | 60 | 1096.1 | 1400.6 |
| poisoning | 80 | 1344.4 | 1635.0 |
| retrieval | 95 | 983.9 | 1398.8 |
| robustness | 55 | 1306.0 | 1663.4 |
| scale | 30 | 669.5 | 1191.9 |
| scope | 75 | 990.9 | 1401.2 |
| silence | 65 | 773.7 | 1407.4 |
| temporal | 75 | 1076.6 | 1409.8 |
| update | 75 | 1164.7 | 1466.6 |

## Answers (L3)

- Verdicts: {'correct': 208, 'partial': 43, 'abstained': 56, 'none': 67, 'hallucinated': 76, 'wrong': 40}
- Judge agreement on a re-judged sample: 94.3% (n=35)

## Cost

- System under test, total: {'calls': 1710, 'embed_calls': 112386, 'embedded_texts': 143861, 'model_calls': 1424, 'cache_hits': 286, 'failures': 0, 'input_tokens': 21162080, 'output_tokens': 646205}
- System under test, during probes by area: {'attribution': {'embed_calls': 144, 'embedded_texts': 169}, 'multi_hop': {'embed_calls': 102, 'embedded_texts': 116}, 'retrieval': {'embed_calls': 149, 'embedded_texts': 180}, 'silence': {'embed_calls': 110, 'embedded_texts': 132}, 'temporal': {'embed_calls': 129, 'embedded_texts': 149}, 'update': {'embed_calls': 129, 'embedded_texts': 155}, 'scope': {'embed_calls': 124, 'embedded_texts': 145}, 'scale': {'embed_calls': 49, 'embedded_texts': 51}, 'application': {'embed_calls': 90, 'embedded_texts': 123}, 'capture': {'embed_calls': 189, 'embedded_texts': 231}, 'consolidation': {'embed_calls': 93, 'embedded_texts': 119}, 'robustness': {'embed_calls': 92, 'embedded_texts': 101}, 'abstention': {'embed_calls': 106, 'embedded_texts': 134}, 'forget': {'embed_calls': 133, 'embedded_texts': 160}, 'poisoning': {'embed_calls': 131, 'embedded_texts': 144}}
- Upkeep per replayed world day (system cost outside probes, 510 days replayed): {'calls': 3.35, 'model_calls': 2.79, 'input_tokens': 41494.27, 'output_tokens': 1267.07}
- Harness models (answerer and judge): {'calls': 1078, 'cache_hits': 394, 'failures': 0, 'input_tokens': 4337682, 'output_tokens': 265300, 'cost_usd': 29.010711599999993}

Per-case results are withheld for the test split.
