# EV3: question-first evaluation

Code: `ev3-code` (`3978d3737c2cc172e5aeb86705136be10471746c`); pinned llm-setup `4c8ccbff21ab4a5fd18ede8a93b73cb11c5749e2` plus the user-authorized replica port patch. Model, engine, protocols, prompts and scoring code were not changed.

Status counts (out of 20 question/corpus pairs): engine=20, rag=20, agent=20, score=20.

## Main table

A is extraction F1. B: effect association accuracy; inventory clean share; consistency claim accuracy; best kind accuracy. C: effect label correct / direction accuracy / completeness; inventory precision / recall / F1; consistency per-study accuracy / completeness; best winner correct / per-study accuracy / completeness. The accuracy columns count only decidable papers, including omitted decidable papers as wrong.

Cost is calls / input tokens / output tokens / seconds; agent cost reports its recorded total tokens and mapping tokens separately because the outcome does not split agent input/output tokens. Cached calls are counted too. Missing data is not zero.

| corpus | question | system | A (f1) | B | C | cost |
|---|---|---|---|---|---|---|
| rag-claude-s1-mixed | rag-factuality | evidence-engine | 0.844 | 0.958 | yes / 0.950 / 0.950 | 66 / 79096 / 12182 / 164.894 |
| rag-claude-s1-mixed | rag-factuality | rag-baseline | - | - | yes / 0.050 / 0.250 | 2 / 2680 / 540 / - |
| rag-claude-s1-mixed | rag-factuality | agent-baseline | - | - | yes / 0.800 / 1.000 | 22 calls; agent tokens=215514; mapping in/out=1337/603; seconds=-; exit=submitted; steps=21/60 |
| rag-claude-s1-mixed | rag-hallucination | evidence-engine | 0.640 | 0.325 | no / 0.667 / 0.667 | 144 / 66206 / 7483 / 88.931 |
| rag-claude-s1-mixed | rag-hallucination | rag-baseline | - | - | no / 0.444 / 0.556 | 2 / 3093 / 499 / - |
| rag-claude-s1-mixed | rag-hallucination | agent-baseline | - | - | yes / 0.889 / 1.000 | 62 calls; agent tokens=1473634; mapping in/out=1693/233; seconds=-; exit=submitted; steps=60/60 |
| rag-claude-s1-mixed | rag-latency | evidence-engine | 0.629 | 0.796 | yes / 1.000 / 1.000 | 148 / 63014 / 7024 / 99.830 |
| rag-claude-s1-mixed | rag-latency | rag-baseline | - | - | no / 0.000 / 0.333 | 2 / 3086 / 280 / - |
| rag-claude-s1-mixed | rag-latency | agent-baseline | - | - | yes / 0.333 / 1.000 | 64 calls; agent tokens=1840249; mapping in/out=1536/111; seconds=-; exit=submitted; steps=60/60 |
| rag-claude-s1-mixed | inv-metrics | evidence-engine | 0.615 | 0.750 | 0.333 / 1.000 / 0.500 | 106 / 43956 / 3901 / 46.158 |
| rag-claude-s1-mixed | inv-metrics | rag-baseline | - | - | 0.750 / 0.857 / 0.800 | 2 / 3077 / 635 / - |
| rag-claude-s1-mixed | inv-metrics | agent-baseline | - | - | 1.000 / 1.000 / 1.000 | 25 calls; agent tokens=246035; mapping in/out=1712/249; seconds=-; exit=submitted; steps=24/60 |
| rag-claude-s1-mixed | inv-methods | evidence-engine | 0.953 | 0.167 | 0.700 / 1.000 / 0.824 | 43 / 43370 / 5959 / 64.077 |
| rag-claude-s1-mixed | inv-methods | rag-baseline | - | - | 0.333 / 0.214 / 0.261 | 2 / 3381 / 1324 / - |
| rag-claude-s1-mixed | inv-methods | agent-baseline | - | - | 0.250 / 0.643 / 0.360 | 55 calls; agent tokens=1323145; mapping in/out=2510/1852; seconds=-; exit=submitted; steps=52/60 |
| rag-claude-s1-mixed | inv-datasets | evidence-engine | 0.814 | 1.000 | 0.500 / 1.000 / 0.667 | 114 / 49863 / 3974 / 46.870 |
| rag-claude-s1-mixed | inv-datasets | rag-baseline | - | - | 1.000 / 0.556 / 0.714 | 2 / 3190 / 419 / - |
| rag-claude-s1-mixed | inv-datasets | agent-baseline | - | - | 1.000 / 0.889 / 0.941 | 39 calls; agent tokens=357279; mapping in/out=1595/225; seconds=-; exit=submitted; steps=37/60 |
| rag-claude-s1-mixed | cons-accuracy | evidence-engine | 0.736 | 1.000 | 0.909 / 0.909 | 124 / 70324 / 11186 / 164.675 |
| rag-claude-s1-mixed | cons-accuracy | rag-baseline | - | - | 0.182 / 0.273 | 2 / 3712 / 1452 / - |
| rag-claude-s1-mixed | cons-accuracy | agent-baseline | - | - | 0.909 / 1.000 | 41 calls; agent tokens=553907; mapping in/out=2058/458; seconds=-; exit=submitted; steps=40/60 |
| rag-claude-s1-mixed | cons-hallucination | evidence-engine | 0.640 | 1.000 | 0.667 / 0.667 | 144 / 66206 / 7465 / 82.779 |
| rag-claude-s1-mixed | cons-hallucination | rag-baseline | - | - | 0.111 / 0.111 | 2 / 2814 / 403 / - |
| rag-claude-s1-mixed | cons-hallucination | agent-baseline | - | - | 0.333 / 0.778 | 30 calls; agent tokens=217531; mapping in/out=1756/165; seconds=-; exit=submitted; steps=28/60 |
| rag-claude-s1-mixed | best-accuracy | evidence-engine | 0.886 | 1.000 | yes / 0.909 / 1.000 | 65 / 38943 / 3875 / 46.298 |
| rag-claude-s1-mixed | best-accuracy | rag-baseline | - | - | no / 0.091 / 0.091 | 2 / 4263 / 1330 / - |
| rag-claude-s1-mixed | best-accuracy | agent-baseline | - | - | no / 0.091 / 0.091 | 22 calls; agent tokens=149259; mapping in/out=1502/30; seconds=-; exit=submitted; steps=21/60 |
| rag-claude-s1-mixed | best-hallucination | evidence-engine | 0.859 | 1.000 | yes / 0.667 / 0.667 | 90 / 44447 / 4323 / 59.858 |
| rag-claude-s1-mixed | best-hallucination | rag-baseline | - | - | no / 0.333 / 0.333 | 2 / 3378 / 572 / - |
| rag-claude-s1-mixed | best-hallucination | agent-baseline | - | - | yes / 1.000 / 1.000 | 26 calls; agent tokens=240569; mapping in/out=2065/211; seconds=-; exit=submitted; steps=25/60 |
| rag-tpl-hard-complex | rag-factuality | evidence-engine | 0.790 | 0.815 | yes / 0.810 / 1.000 | 428 / 540484 / 126967 / 1203.959 |
| rag-tpl-hard-complex | rag-factuality | rag-baseline | - | - | yes / 0.050 / 0.060 | 2 / 3495 / 901 / - |
| rag-tpl-hard-complex | rag-factuality | agent-baseline | - | - | yes / 1.000 / 1.000 | 35 calls; agent tokens=364900; mapping in/out=1937/3168; seconds=-; exit=submitted; steps=34/60 |
| rag-tpl-hard-complex | rag-hallucination | evidence-engine | 0.650 | 0.554 | yes / 0.814 / 0.915 | 862 / 507000 / 104132 / 1020.830 |
| rag-tpl-hard-complex | rag-hallucination | rag-baseline | - | - | no / 0.000 / 0.102 | 2 / 2890 / 665 / - |
| rag-tpl-hard-complex | rag-hallucination | agent-baseline | - | - | no / 0.000 / 0.000 | 11 calls; agent tokens=65376; mapping in/out=2113/56; seconds=-; exit=submitted; steps=9/60 |
| rag-tpl-hard-complex | rag-latency | evidence-engine | 0.674 | 0.651 | yes / 0.942 / 0.962 | 644 / 371943 / 69834 / 712.604 |
| rag-tpl-hard-complex | rag-latency | rag-baseline | - | - | no / 0.019 / 0.019 | 2 / 2872 / 259 / - |
| rag-tpl-hard-complex | rag-latency | agent-baseline | - | - | yes / 0.115 / 0.154 | 62 calls; agent tokens=1543134; mapping in/out=2295/215; seconds=-; exit=submitted; steps=60/60 |
| rag-tpl-hard-complex | inv-metrics | evidence-engine | 0.712 | 1.000 | 0.400 / 1.000 / 0.571 | 590 / 249500 / 31027 / 330.786 |
| rag-tpl-hard-complex | inv-metrics | rag-baseline | - | - | 1.000 / 0.625 / 0.769 | 2 / 3221 / 606 / - |
| rag-tpl-hard-complex | inv-metrics | agent-baseline | - | - | 1.000 / 1.000 / 1.000 | 46 calls; agent tokens=936661; mapping in/out=3652/1371; seconds=-; exit=submitted; steps=44/60 |
| rag-tpl-hard-complex | inv-methods | evidence-engine | 1.000 | 1.000 | 1.000 / 1.000 / 1.000 | 240 / 244578 / 33781 / 339.690 |
| rag-tpl-hard-complex | inv-methods | rag-baseline | - | - | 0.000 / 0.000 / 0.000 | 2 / 3334 / 857 / - |
| rag-tpl-hard-complex | inv-methods | agent-baseline | - | - | 0.615 / 0.286 / 0.390 | 50 calls; agent tokens=887636; mapping in/out=4724/1544; seconds=-; exit=submitted; steps=48/60 |
| rag-tpl-hard-complex | inv-datasets | evidence-engine | 0.900 | 1.000 | 0.625 / 1.000 / 0.769 | 572 / 216642 / 21338 / 236.692 |
| rag-tpl-hard-complex | inv-datasets | rag-baseline | - | - | 1.000 / 0.400 / 0.571 | 2 / 2951 / 372 / - |
| rag-tpl-hard-complex | inv-datasets | agent-baseline | - | - | 1.000 / 1.000 / 1.000 | 43 calls; agent tokens=663074; mapping in/out=3684/1395; seconds=-; exit=submitted; steps=41/60 |
| rag-tpl-hard-complex | cons-accuracy | evidence-engine | 0.689 | 1.000 | 0.641 / 0.897 | 686 / 391175 / 80227 / 757.207 |
| rag-tpl-hard-complex | cons-accuracy | rag-baseline | - | - | 0.026 / 0.026 | 2 / 13718 / 7941 / - |
| rag-tpl-hard-complex | cons-accuracy | agent-baseline | - | - | 1.000 / 1.000 | 32 calls; agent tokens=500564; mapping in/out=2486/2420; seconds=-; exit=submitted; steps=30/60 |
| rag-tpl-hard-complex | cons-hallucination | evidence-engine | 0.646 | 1.000 | 0.800 / 0.891 | 856 / 501307 / 101602 / 937.216 |
| rag-tpl-hard-complex | cons-hallucination | rag-baseline | - | - | 0.000 / 0.000 | 2 / 3686 / 636 / - |
| rag-tpl-hard-complex | cons-hallucination | agent-baseline | - | - | 0.000 / 0.000 | 14 calls; agent tokens=88597; mapping in/out=1985/7; seconds=-; exit=submitted; steps=12/60 |
| rag-tpl-hard-complex | best-accuracy | evidence-engine | 0.872 | 1.000 | yes / 0.650 / 1.000 | 404 / 205488 / 23944 / 240.362 |
| rag-tpl-hard-complex | best-accuracy | rag-baseline | - | - | yes / 0.000 / 0.000 | 2 / 3420 / 369 / - |
| rag-tpl-hard-complex | best-accuracy | agent-baseline | - | - | no / 0.000 / 0.000 | 17 calls; agent tokens=135590; mapping in/out=2370/7; seconds=-; exit=submitted; steps=15/60 |
| rag-tpl-hard-complex | best-hallucination | evidence-engine | 0.859 | 1.000 | yes / 0.561 / 0.895 | 611 / 397223 / 140477 / 1239.660 |
| rag-tpl-hard-complex | best-hallucination | rag-baseline | - | - | yes / 0.018 / 0.018 | 2 / 3494 / 354 / - |
| rag-tpl-hard-complex | best-hallucination | agent-baseline | - | - | yes / 0.509 / 0.947 | 54 calls; agent tokens=876057; mapping in/out=9368/1913; seconds=-; exit=submitted; steps=52/60 |

Scored evidence types (A is comparable within a question):

- `rag-factuality`: condition, metric, measurement, author_claim
- `rag-hallucination`: condition, metric, measurement, author_claim
- `rag-latency`: condition, metric, measurement
- `inv-metrics`: metric
- `inv-methods`: condition
- `inv-datasets`: dataset
- `cons-accuracy`: condition, metric, measurement, author_claim
- `cons-hallucination`: condition, metric, measurement, author_claim
- `best-accuracy`: condition, metric, measurement
- `best-hallucination`: condition, metric, measurement

## Per-extractor A

These are per-type rows at level all. Cascade extractors see remaining gaps, so these are marginal contributions rather than standalone extraction scores.

| corpus | question | extractor | type | precision | recall | f1 |
|---|---|---|---|---|---|---|
| rag-claude-s1-mixed | rag-factuality | llm_condition@1#45b3761c700e | condition | 1.000 | 0.583 | 0.737 |
| rag-claude-s1-mixed | rag-factuality | llm_measurement@1#02bd5a7ab104 | measurement | 0.940 | 0.653 | 0.770 |
| rag-claude-s1-mixed | rag-factuality | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | rag-factuality | regex_author_claim@2#fd7877790c48 | author_claim | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | rag-factuality | regex_condition@2#0a5bf730763c | condition | 1.000 | 0.377 | 0.548 |
| rag-claude-s1-mixed | rag-factuality | regex_measurement@2#e2d17eb260ea | measurement | 0.849 | 0.275 | 0.415 |
| rag-claude-s1-mixed | rag-factuality | regex_metric@2#0affe2d9ce77 | metric | 0.958 | 0.852 | 0.902 |
| rag-claude-s1-mixed | rag-hallucination | abbrev_condition@1#8587f7b799e0 | condition | 1.000 | 0.056 | 0.105 |
| rag-claude-s1-mixed | rag-hallucination | abbrev_metric@1#1c52ebcdca5c | metric | 1.000 | 0.095 | 0.174 |
| rag-claude-s1-mixed | rag-hallucination | gliner_condition@1#6df192dba74f | condition | 0.194 | 0.333 | 0.245 |
| rag-claude-s1-mixed | rag-hallucination | gliner_metric@1#cdbeb73388e0 | metric | 0.567 | 0.809 | 0.667 |
| rag-claude-s1-mixed | rag-hallucination | llm_condition@1#45b3761c700e | condition | 0.960 | 0.667 | 0.787 |
| rag-claude-s1-mixed | rag-hallucination | llm_measurement@1#02bd5a7ab104 | measurement | 0.800 | 0.667 | 0.727 |
| rag-claude-s1-mixed | rag-hallucination | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.762 | 0.865 |
| rag-claude-s1-mixed | rag-hallucination | number_measurement@1#d7f39465e8e3 | measurement | 1.000 | 0.333 | 0.500 |
| rag-claude-s1-mixed | rag-hallucination | regex_author_claim@2#f0e017f040b9 | author_claim | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | rag-hallucination | regex_condition@2#dacfca378fed | condition | 0.957 | 0.361 | 0.524 |
| rag-claude-s1-mixed | rag-hallucination | regex_measurement@2#8955e245e6dd | measurement | 0.939 | 0.304 | 0.459 |
| rag-claude-s1-mixed | rag-hallucination | regex_metric@2#ae09439dbca7 | metric | 0.750 | 0.667 | 0.706 |
| rag-claude-s1-mixed | rag-latency | abbrev_condition@1#ea9c557ddc1a | condition | 0.500 | 0.028 | 0.053 |
| rag-claude-s1-mixed | rag-latency | abbrev_metric@1#52506d2e3a69 | metric | 1.000 | 0.235 | 0.381 |
| rag-claude-s1-mixed | rag-latency | gliner_condition@1#c8fde69a32e1 | condition | 0.177 | 0.306 | 0.225 |
| rag-claude-s1-mixed | rag-latency | gliner_metric@1#ce2c7d899fd3 | metric | 0.500 | 0.824 | 0.622 |
| rag-claude-s1-mixed | rag-latency | llm_condition@1#45b3761c700e | condition | 0.966 | 0.778 | 0.862 |
| rag-claude-s1-mixed | rag-latency | llm_measurement@1#4171ae269b7f | measurement | 0.833 | 0.278 | 0.417 |
| rag-claude-s1-mixed | rag-latency | llm_metric@1#f77fae6f7754 | metric | 1.000 | 0.882 | 0.938 |
| rag-claude-s1-mixed | rag-latency | number_measurement@1#9489bf6f9408 | measurement | 0.958 | 0.767 | 0.852 |
| rag-claude-s1-mixed | rag-latency | regex_condition@2#1d6558c26117 | condition | 0.913 | 0.344 | 0.500 |
| rag-claude-s1-mixed | rag-latency | regex_measurement_units@1#a0d7822bd8cd | measurement | 0.897 | 0.255 | 0.397 |
| rag-claude-s1-mixed | rag-latency | regex_metric@2#7b60cc978d29 | metric | 0.652 | 0.556 | 0.600 |
| rag-claude-s1-mixed | inv-metrics | abbrev_metric@1#8bc3c347fdea | metric | 1.000 | 0.148 | 0.258 |
| rag-claude-s1-mixed | inv-metrics | gliner_metric@1#13cd7bab1b65 | metric | 0.512 | 0.815 | 0.629 |
| rag-claude-s1-mixed | inv-metrics | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.815 | 0.898 |
| rag-claude-s1-mixed | inv-metrics | regex_metric@2#d4eacbf703f6 | metric | 0.750 | 0.667 | 0.706 |
| rag-claude-s1-mixed | inv-methods | llm_condition@1#f409ef68fc87 | condition | 0.902 | 0.902 | 0.902 |
| rag-claude-s1-mixed | inv-methods | regex_condition_kind@1#f81a9016cc8b | condition | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | inv-datasets | gliner_dataset@1#bbf10b224d67 | dataset | 0.686 | 1.000 | 0.814 |
| rag-claude-s1-mixed | inv-datasets | llm_dataset@1#0657dd619876 | dataset | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | inv-datasets | regex_dataset@1#85380ccc622a | dataset | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | cons-accuracy | abbrev_condition@1#eafcbe39d1a0 | condition | 1.000 | 0.056 | 0.105 |
| rag-claude-s1-mixed | cons-accuracy | abbrev_metric@1#dac5a8a5c84b | metric | 1.000 | 0.250 | 0.400 |
| rag-claude-s1-mixed | cons-accuracy | gliner_condition@1#52e6222ffa49 | condition | 0.194 | 0.333 | 0.245 |
| rag-claude-s1-mixed | cons-accuracy | gliner_metric@1#0a7a21786921 | metric | 0.385 | 0.625 | 0.476 |
| rag-claude-s1-mixed | cons-accuracy | llm_condition@1#45b3761c700e | condition | 0.960 | 0.667 | 0.787 |
| rag-claude-s1-mixed | cons-accuracy | llm_measurement@1#02bd5a7ab104 | measurement | 0.763 | 0.674 | 0.716 |
| rag-claude-s1-mixed | cons-accuracy | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.750 | 0.857 |
| rag-claude-s1-mixed | cons-accuracy | number_measurement@1#a78269e0513d | measurement | 0.850 | 0.618 | 0.716 |
| rag-claude-s1-mixed | cons-accuracy | regex_author_claim@2#c58240a3a7a4 | author_claim | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | cons-accuracy | regex_condition@2#207f8f280e4a | condition | 0.957 | 0.361 | 0.524 |
| rag-claude-s1-mixed | cons-accuracy | regex_measurement@2#a65f61f0d966 | measurement | 0.839 | 0.255 | 0.391 |
| rag-claude-s1-mixed | cons-accuracy | regex_metric@2#a5a76405f5d5 | metric | 0.958 | 0.852 | 0.902 |
| rag-claude-s1-mixed | cons-hallucination | abbrev_condition@1#8587f7b799e0 | condition | 1.000 | 0.056 | 0.105 |
| rag-claude-s1-mixed | cons-hallucination | abbrev_metric@1#1c52ebcdca5c | metric | 1.000 | 0.095 | 0.174 |
| rag-claude-s1-mixed | cons-hallucination | gliner_condition@1#6df192dba74f | condition | 0.194 | 0.333 | 0.245 |
| rag-claude-s1-mixed | cons-hallucination | gliner_metric@1#cdbeb73388e0 | metric | 0.567 | 0.809 | 0.667 |
| rag-claude-s1-mixed | cons-hallucination | llm_condition@1#45b3761c700e | condition | 0.960 | 0.667 | 0.787 |
| rag-claude-s1-mixed | cons-hallucination | llm_measurement@1#02bd5a7ab104 | measurement | 0.800 | 0.667 | 0.727 |
| rag-claude-s1-mixed | cons-hallucination | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.762 | 0.865 |
| rag-claude-s1-mixed | cons-hallucination | number_measurement@1#d7f39465e8e3 | measurement | 1.000 | 0.333 | 0.500 |
| rag-claude-s1-mixed | cons-hallucination | regex_author_claim@2#f0e017f040b9 | author_claim | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | cons-hallucination | regex_condition@2#dacfca378fed | condition | 0.957 | 0.361 | 0.524 |
| rag-claude-s1-mixed | cons-hallucination | regex_measurement@2#8955e245e6dd | measurement | 0.939 | 0.304 | 0.459 |
| rag-claude-s1-mixed | cons-hallucination | regex_metric@2#ae09439dbca7 | metric | 0.750 | 0.667 | 0.706 |
| rag-claude-s1-mixed | best-accuracy | abbrev_metric@1#1d39e83ec7bc | metric | 1.000 | 0.222 | 0.364 |
| rag-claude-s1-mixed | best-accuracy | gliner_metric@1#81459b8621e8 | metric | 0.357 | 0.556 | 0.435 |
| rag-claude-s1-mixed | best-accuracy | llm_measurement@1#02bd5a7ab104 | measurement | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | best-accuracy | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.556 | 0.714 |
| rag-claude-s1-mixed | best-accuracy | number_measurement@1#460574ff54d0 | measurement | 1.000 | 0.308 | 0.471 |
| rag-claude-s1-mixed | best-accuracy | regex_condition_kind@1#2d8734025944 | condition | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | best-accuracy | regex_measurement@2#ad0dd5c19f1c | measurement | 1.000 | 0.598 | 0.749 |
| rag-claude-s1-mixed | best-accuracy | regex_metric@2#b7c72c33bc59 | metric | 0.958 | 0.852 | 0.902 |
| rag-claude-s1-mixed | best-hallucination | abbrev_metric@1#2ec10bd35b5b | metric | 1.000 | 0.091 | 0.167 |
| rag-claude-s1-mixed | best-hallucination | gliner_metric@1#32fb264e295d | metric | 0.548 | 0.773 | 0.641 |
| rag-claude-s1-mixed | best-hallucination | llm_measurement@1#02bd5a7ab104 | measurement | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | best-hallucination | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.591 | 0.743 |
| rag-claude-s1-mixed | best-hallucination | number_measurement@1#f8148ede3708 | measurement | 0.636 | 0.467 | 0.538 |
| rag-claude-s1-mixed | best-hallucination | regex_condition_kind@1#0a9f7d82195a | condition | 1.000 | 1.000 | 1.000 |
| rag-claude-s1-mixed | best-hallucination | regex_measurement@2#b29c53384eb5 | measurement | 1.000 | 0.598 | 0.749 |
| rag-claude-s1-mixed | best-hallucination | regex_metric@2#0e8a190b4722 | metric | 0.750 | 0.667 | 0.706 |
| rag-tpl-hard-complex | rag-factuality | llm_condition@1#45b3761c700e | condition | 1.000 | 0.613 | 0.760 |
| rag-tpl-hard-complex | rag-factuality | llm_measurement@1#02bd5a7ab104 | measurement | 0.941 | 0.389 | 0.550 |
| rag-tpl-hard-complex | rag-factuality | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.845 | 0.916 |
| rag-tpl-hard-complex | rag-factuality | regex_author_claim@2#fd7877790c48 | author_claim | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | rag-factuality | regex_condition@2#0a5bf730763c | condition | 0.994 | 0.485 | 0.652 |
| rag-tpl-hard-complex | rag-factuality | regex_measurement@2#e2d17eb260ea | measurement | 0.918 | 0.324 | 0.479 |
| rag-tpl-hard-complex | rag-factuality | regex_metric@2#0affe2d9ce77 | metric | 1.000 | 0.821 | 0.902 |
| rag-tpl-hard-complex | rag-hallucination | abbrev_condition@1#8587f7b799e0 | condition | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | rag-hallucination | abbrev_metric@1#1c52ebcdca5c | metric | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | rag-hallucination | gliner_condition@1#6df192dba74f | condition | 0.372 | 0.584 | 0.455 |
| rag-tpl-hard-complex | rag-hallucination | gliner_metric@1#cdbeb73388e0 | metric | 0.522 | 0.790 | 0.629 |
| rag-tpl-hard-complex | rag-hallucination | llm_condition@1#45b3761c700e | condition | 1.000 | 0.890 | 0.942 |
| rag-tpl-hard-complex | rag-hallucination | llm_measurement@1#02bd5a7ab104 | measurement | 0.639 | 0.276 | 0.386 |
| rag-tpl-hard-complex | rag-hallucination | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.844 | 0.915 |
| rag-tpl-hard-complex | rag-hallucination | number_measurement@1#d7f39465e8e3 | measurement | 0.681 | 0.313 | 0.429 |
| rag-tpl-hard-complex | rag-hallucination | regex_author_claim@2#f0e017f040b9 | author_claim | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | rag-hallucination | regex_condition@2#dacfca378fed | condition | 0.982 | 0.479 | 0.644 |
| rag-tpl-hard-complex | rag-hallucination | regex_measurement@2#8955e245e6dd | measurement | 0.943 | 0.241 | 0.384 |
| rag-tpl-hard-complex | rag-hallucination | regex_metric@2#ae09439dbca7 | metric | 0.884 | 0.726 | 0.797 |
| rag-tpl-hard-complex | rag-latency | abbrev_condition@1#ea9c557ddc1a | condition | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | rag-latency | abbrev_metric@1#52506d2e3a69 | metric | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | rag-latency | gliner_condition@1#c8fde69a32e1 | condition | 0.372 | 0.584 | 0.455 |
| rag-tpl-hard-complex | rag-latency | gliner_metric@1#ce2c7d899fd3 | metric | 0.696 | 0.918 | 0.791 |
| rag-tpl-hard-complex | rag-latency | llm_condition@1#45b3761c700e | condition | 1.000 | 0.876 | 0.934 |
| rag-tpl-hard-complex | rag-latency | llm_measurement@1#4171ae269b7f | measurement | 0.861 | 0.370 | 0.517 |
| rag-tpl-hard-complex | rag-latency | llm_metric@1#f77fae6f7754 | metric | 0.885 | 0.885 | 0.885 |
| rag-tpl-hard-complex | rag-latency | number_measurement@1#9489bf6f9408 | measurement | 0.904 | 0.517 | 0.657 |
| rag-tpl-hard-complex | rag-latency | regex_condition@2#1d6558c26117 | condition | 0.982 | 0.479 | 0.644 |
| rag-tpl-hard-complex | rag-latency | regex_measurement_units@1#a0d7822bd8cd | measurement | 0.952 | 0.312 | 0.469 |
| rag-tpl-hard-complex | rag-latency | regex_metric@2#7b60cc978d29 | metric | 0.889 | 0.730 | 0.802 |
| rag-tpl-hard-complex | inv-metrics | abbrev_metric@1#8bc3c347fdea | metric | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | inv-metrics | gliner_metric@1#13cd7bab1b65 | metric | 0.535 | 0.821 | 0.648 |
| rag-tpl-hard-complex | inv-metrics | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | inv-metrics | regex_metric@2#d4eacbf703f6 | metric | 0.884 | 0.726 | 0.797 |
| rag-tpl-hard-complex | inv-methods | llm_condition@1#f409ef68fc87 | condition | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | inv-methods | regex_condition_kind@1#f81a9016cc8b | condition | 1.000 | 0.943 | 0.971 |
| rag-tpl-hard-complex | inv-datasets | gliner_dataset@1#bbf10b224d67 | dataset | 0.815 | 0.976 | 0.888 |
| rag-tpl-hard-complex | inv-datasets | llm_dataset@1#0657dd619876 | dataset | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | inv-datasets | regex_dataset@1#85380ccc622a | dataset | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | cons-accuracy | abbrev_condition@1#eafcbe39d1a0 | condition | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | cons-accuracy | abbrev_metric@1#dac5a8a5c84b | metric | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | cons-accuracy | gliner_condition@1#52e6222ffa49 | condition | 0.377 | 0.591 | 0.460 |
| rag-tpl-hard-complex | cons-accuracy | gliner_metric@1#0a7a21786921 | metric | 0.448 | 0.697 | 0.545 |
| rag-tpl-hard-complex | cons-accuracy | llm_condition@1#45b3761c700e | condition | 1.000 | 0.869 | 0.930 |
| rag-tpl-hard-complex | cons-accuracy | llm_measurement@1#02bd5a7ab104 | measurement | 0.874 | 0.506 | 0.641 |
| rag-tpl-hard-complex | cons-accuracy | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.948 | 0.974 |
| rag-tpl-hard-complex | cons-accuracy | number_measurement@1#a78269e0513d | measurement | 0.906 | 0.633 | 0.745 |
| rag-tpl-hard-complex | cons-accuracy | regex_author_claim@2#c58240a3a7a4 | author_claim | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | cons-accuracy | regex_condition@2#207f8f280e4a | condition | 0.982 | 0.479 | 0.644 |
| rag-tpl-hard-complex | cons-accuracy | regex_measurement@2#a65f61f0d966 | measurement | 0.930 | 0.310 | 0.466 |
| rag-tpl-hard-complex | cons-accuracy | regex_metric@2#a5a76405f5d5 | metric | 1.000 | 0.821 | 0.902 |
| rag-tpl-hard-complex | cons-hallucination | abbrev_condition@1#8587f7b799e0 | condition | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | cons-hallucination | abbrev_metric@1#1c52ebcdca5c | metric | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | cons-hallucination | gliner_condition@1#6df192dba74f | condition | 0.377 | 0.591 | 0.460 |
| rag-tpl-hard-complex | cons-hallucination | gliner_metric@1#cdbeb73388e0 | metric | 0.524 | 0.792 | 0.631 |
| rag-tpl-hard-complex | cons-hallucination | llm_condition@1#45b3761c700e | condition | 1.000 | 0.854 | 0.921 |
| rag-tpl-hard-complex | cons-hallucination | llm_measurement@1#02bd5a7ab104 | measurement | 0.636 | 0.272 | 0.381 |
| rag-tpl-hard-complex | cons-hallucination | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.855 | 0.922 |
| rag-tpl-hard-complex | cons-hallucination | number_measurement@1#d7f39465e8e3 | measurement | 0.682 | 0.304 | 0.421 |
| rag-tpl-hard-complex | cons-hallucination | regex_author_claim@2#f0e017f040b9 | author_claim | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | cons-hallucination | regex_condition@2#dacfca378fed | condition | 0.982 | 0.479 | 0.644 |
| rag-tpl-hard-complex | cons-hallucination | regex_measurement@2#8955e245e6dd | measurement | 0.949 | 0.240 | 0.384 |
| rag-tpl-hard-complex | cons-hallucination | regex_metric@2#ae09439dbca7 | metric | 0.884 | 0.726 | 0.797 |
| rag-tpl-hard-complex | best-accuracy | abbrev_metric@1#1d39e83ec7bc | metric | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | best-accuracy | gliner_metric@1#81459b8621e8 | metric | 0.448 | 0.697 | 0.545 |
| rag-tpl-hard-complex | best-accuracy | llm_measurement@1#02bd5a7ab104 | measurement | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | best-accuracy | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.961 | 0.980 |
| rag-tpl-hard-complex | best-accuracy | number_measurement@1#460574ff54d0 | measurement | 1.000 | 1.000 | 1.000 |
| rag-tpl-hard-complex | best-accuracy | regex_condition_kind@1#2d8734025944 | condition | 1.000 | 0.943 | 0.971 |
| rag-tpl-hard-complex | best-accuracy | regex_measurement@2#ad0dd5c19f1c | measurement | 1.000 | 0.766 | 0.868 |
| rag-tpl-hard-complex | best-accuracy | regex_metric@2#b7c72c33bc59 | metric | 1.000 | 0.821 | 0.902 |
| rag-tpl-hard-complex | best-hallucination | abbrev_metric@1#2ec10bd35b5b | metric | n/a | 0.000 | 0.000 |
| rag-tpl-hard-complex | best-hallucination | gliner_metric@1#32fb264e295d | metric | 0.522 | 0.790 | 0.629 |
| rag-tpl-hard-complex | best-hallucination | llm_measurement@1#02bd5a7ab104 | measurement | 0.719 | 0.680 | 0.699 |
| rag-tpl-hard-complex | best-hallucination | llm_metric@1#41e1e53a1fc4 | metric | 1.000 | 0.933 | 0.965 |
| rag-tpl-hard-complex | best-hallucination | number_measurement@1#f8148ede3708 | measurement | 0.518 | 0.261 | 0.347 |
| rag-tpl-hard-complex | best-hallucination | regex_condition_kind@1#0a9f7d82195a | condition | 1.000 | 0.943 | 0.971 |
| rag-tpl-hard-complex | best-hallucination | regex_measurement@2#b29c53384eb5 | measurement | 0.934 | 0.563 | 0.702 |
| rag-tpl-hard-complex | best-hallucination | regex_metric@2#0e8a190b4722 | metric | 0.884 | 0.726 | 0.797 |

## Mapping check

| system | question | kind | exit 0 | answer exists | shape | served model | mapping input/output tokens | C | issues |
|---|---|---|---|---|---|---|---|---|---|
| rag | rag-hallucination | effect | yes | yes | studies: 5 | orch-model | 1007/145 | no / 0.444 / 0.556 | none observed |
| rag | inv-metrics | inventory | yes | yes | entries: 8 | orch-model | 1057/162 | 0.750 / 0.857 / 0.800 | none observed |
| rag | cons-accuracy | consistency | yes | yes | studies: 4 | orch-model | 1902/96 | 0.182 / 0.273 | none observed |
| rag | best-accuracy | best | yes | yes | studies: 6 | orch-model | 1956/133 | no / 0.091 / 0.091 | none observed |
| agent | inv-metrics | inventory | yes | yes | entries: 9 | orch-model | 2078/280 | 0.778 / 1.000 / 0.875 | none observed |
| agent | best-accuracy | best | yes | yes | studies: 11 | orch-model | 2609/263 | yes / 1.000 / 1.000 | none observed |

See `logs/mapcheck-local.log` and saved mapping-call records for observed errors and retries. Mapping records do not expose retry counts; the pinned model-call implementation permits at most one validation retry per call.

## GPU, GLiNER and versions

Three NVIDIA A100-SXM4-40GB GPUs; driver `580.159.04`, CUDA `13.0`, vLLM `0.21.0` (measured inside the job). GLiNER started on CUDA and used 1296 MiB; GPU 0 had 3367 MiB free after startup. The profile retained gpu_memory_utilization 0.92; the 0.88 adjustment was unnecessary. GLINER_URL was set to http://127.0.0.1:8090. Readiness checks are in `logs/check-stack.log`.

## Engine health and failures

Served model call counts:

```
Pending final count.
```

| run | failed calls | GLiNER skipped | GLiNER found |
|---|---|---|---|
| best-accuracy-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 14 |
| best-accuracy-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 14 |
| best-accuracy-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 241 |
| best-accuracy-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| best-accuracy-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| best-hallucination-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 31 |
| best-hallucination-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 31 |
| best-hallucination-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 339 |
| best-hallucination-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| best-hallucination-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 0 |
| cascade-gaps/rag-claude-s1-mixed-cf-S001-contradicts | 0 | 0 | 0 |
| cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 0 |
| cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 0 |
| cons-accuracy-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 75 |
| cons-accuracy-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 75 |
| cons-accuracy-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 456 |
| cons-accuracy-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| cons-accuracy-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| cons-hallucination-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 92 |
| cons-hallucination-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 92 |
| cons-hallucination-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 549 |
| cons-hallucination-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| cons-hallucination-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| inv-datasets-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 35 |
| inv-datasets-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 35 |
| inv-datasets-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 254 |
| inv-datasets-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| inv-datasets-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| inv-methods-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 0 |
| inv-methods-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 0 |
| inv-methods-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 0 |
| inv-methods-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| inv-methods-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| inv-metrics-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 43 |
| inv-metrics-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 43 |
| inv-metrics-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 404 |
| inv-metrics-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| inv-metrics-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| rag-factuality-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| rag-factuality-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| rag-hallucination-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 92 |
| rag-hallucination-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 92 |
| rag-hallucination-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 554 |
| rag-hallucination-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| rag-hallucination-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| rag-latency-cascade-gaps/rag-claude-s1-mixed | 0 | 0 | 90 |
| rag-latency-cascade-gaps/rag-claude-s1-mixed-r2 | 0 | 0 | 90 |
| rag-latency-cascade-gaps/rag-tpl-hard-complex | 0 | 0 | 376 |
| rag-latency-llm-only/rag-claude-s1-mixed | 0 | 0 | 0 |
| rag-latency-regex-only/rag-claude-s1-mixed | 0 | 0 | 0 |

Full failure history, commands, actions and startup deviation: [failures.md](failures.md).

Recorded FAIL lines:

| log | failure |
|---|---|
| extras-hard.log | FAIL rag-per-paper-k1 rag-factuality rag-tpl-hard-complex |
| extras-hard.log | FAIL rag-per-paper-k1 rag-hallucination rag-tpl-hard-complex |
| extras-hard.log | FAIL rag-per-paper-k1 inv-metrics rag-tpl-hard-complex |
| extras-hard.log | FAIL rag-per-paper-k1 inv-methods rag-tpl-hard-complex |
| extras-hard.log | FAIL rag-per-paper-k1 inv-datasets rag-tpl-hard-complex |
| extras-main.log | FAIL rag-oracle cons-accuracy rag-claude-s1-mixed |
| grid-hard-corrected.log | FAIL UnexpectedModelBehavior: Exceeded maximum output retries (1) |
| grid-hard-corrected.log | FAIL agent inv-metrics rag-tpl-hard-complex |
| grid-hard-corrected.log | FAIL UnexpectedModelBehavior: Exceeded maximum output retries (1) |
| grid-hard-corrected.log | FAIL agent inv-methods rag-tpl-hard-complex |
| grid-hard.log | FAIL engine rag-factuality rag-claude-s1-hard (exit 1) |
| grid-hard.log | FAIL rag rag-factuality rag-claude-s1-hard |
| grid-hard.log | FAIL agent rag-factuality rag-claude-s1-hard |
| grid-hard.log | FAIL score rag-factuality rag-claude-s1-hard: no answer to score |
| grid-hard.log | FAIL engine rag-hallucination rag-claude-s1-hard (exit 1) |
| grid-hard.log | FAIL rag rag-hallucination rag-claude-s1-hard |
| retry-hard-agents.log | FAIL UnexpectedModelBehavior: Exceeded maximum output retries (1) |
| retry-hard-agents.log | FAIL agent inv-methods rag-tpl-hard-complex |
| retry-hard-per-paper-last.log | FAIL rag-per-paper-k1 inv-metrics rag-tpl-hard-complex |
| retry-hard-per-paper-last.log | FAIL rag-per-paper-k1 inv-methods rag-tpl-hard-complex |
| retry-hard-per-paper-last.log | FAIL rag-per-paper-k1 inv-datasets rag-tpl-hard-complex |
| retry-hard-per-paper.log | FAIL rag-per-paper-k1 inv-metrics rag-tpl-hard-complex |
| retry-hard-per-paper.log | FAIL rag-per-paper-k1 inv-methods rag-tpl-hard-complex |
| retry-hard-per-paper.log | FAIL rag-per-paper-k1 inv-datasets rag-tpl-hard-complex |

## Extra comparisons

The per-paper RAG row is the fair RAG comparison for C: every paper is seen, so a left-out paper is the model’s choice. The oracle passage row is a diagnostic that intentionally uses ground truth. Regex-only and LLM-only are standalone rows; cascade gains are relative to them.

| corpus | question | system | A (f1) | B | C | cost |
|---|---|---|---|---|---|---|
| rag-claude-s1-mixed | best-accuracy | engine-r2 | 0.886 | 1.000 | yes / 0.909 / 1.000 | 65 / 38943 / 3857 / 40.201 |
| rag-claude-s1-mixed | best-accuracy | llm-only | 0.948 | 1.000 | yes / 1.000 / 1.000 | 109 / 132267 / 26241 / 292.595 |
| rag-claude-s1-mixed | best-accuracy | rag-oracle | - | - | yes / 1.000 / 1.000 | 2 / 12242 / 2087 / - |
| rag-claude-s1-mixed | best-accuracy | rag-per-paper | - | - | no / 0.727 / 0.727 | 2 / 13034 / 2535 / - |
| rag-claude-s1-mixed | best-accuracy | rag-seed1 | - | - | no / 0.091 / 0.182 | 2 / 4719 / 1737 / - |
| rag-claude-s1-mixed | best-accuracy | rag-seed2 | - | - | no / 0.091 / 0.091 | 2 / 4263 / 1330 / - |
| rag-claude-s1-mixed | best-accuracy | regex-only | 0.876 | 1.000 | no / 0.636 / 0.727 | 0 / 0 / 0 / 2.209 |
| rag-claude-s1-mixed | best-hallucination | engine-r2 | 0.859 | 1.000 | yes / 0.667 / 0.667 | 90 / 44447 / 4508 / 53.399 |
| rag-claude-s1-mixed | best-hallucination | llm-only | 0.948 | 1.000 | yes / 0.556 / 0.556 | 109 / 132267 / 26243 / 295.798 |
| rag-claude-s1-mixed | best-hallucination | rag-oracle | - | - | yes / 1.000 / 1.000 | 2 / 11560 / 970 / - |
| rag-claude-s1-mixed | best-hallucination | rag-per-paper | - | - | yes / 0.556 / 0.667 | 2 / 11946 / 842 / - |
| rag-claude-s1-mixed | best-hallucination | rag-seed1 | - | - | yes / 0.556 / 0.556 | 2 / 3413 / 563 / - |
| rag-claude-s1-mixed | best-hallucination | rag-seed2 | - | - | no / 0.333 / 0.333 | 2 / 3378 / 572 / - |
| rag-claude-s1-mixed | best-hallucination | regex-only | 0.884 | 1.000 | no / 0.333 / 0.333 | 0 / 0 / 0 / 2.342 |
| rag-claude-s1-mixed | cons-accuracy | engine-r2 | 0.739 | 1.000 | 0.909 / 0.909 | 124 / 70324 / 11266 / 158.735 |
| rag-claude-s1-mixed | cons-accuracy | llm-only | 0.933 | 1.000 | 1.000 / 1.000 | 129 / 150395 / 28338 / 318.394 |
| rag-claude-s1-mixed | cons-accuracy | rag-oracle | - | - | 0.909 / 0.909 | 2 / 13265 / 3145 / - |
| rag-claude-s1-mixed | cons-accuracy | rag-per-paper | - | - | 0.091 / 0.091 | 2 / 22160 / 5086 / - |
| rag-claude-s1-mixed | cons-accuracy | rag-seed1 | - | - | 0.000 / 0.091 | 2 / 2726 / 332 / - |
| rag-claude-s1-mixed | cons-accuracy | rag-seed2 | - | - | 0.182 / 0.273 | 2 / 3712 / 1452 / - |
| rag-claude-s1-mixed | cons-accuracy | regex-only | 0.626 | 1.000 | 0.273 / 0.273 | 0 / 0 / 0 / 2.604 |
| rag-claude-s1-mixed | cons-hallucination | engine-r2 | 0.640 | 1.000 | 0.667 / 0.667 | 145 / 67372 / 7558 / 82.013 |
| rag-claude-s1-mixed | cons-hallucination | llm-only | 0.933 | 1.000 | 0.556 / 0.556 | 129 / 150595 / 28333 / 309.509 |
| rag-claude-s1-mixed | cons-hallucination | rag-oracle | - | - | 0.889 / 0.889 | 2 / 13181 / 2735 / - |
| rag-claude-s1-mixed | cons-hallucination | rag-per-paper | - | - | 0.667 / 0.667 | 2 / 10962 / 814 / - |
| rag-claude-s1-mixed | cons-hallucination | rag-seed1 | - | - | 0.111 / 0.111 | 2 / 2814 / 403 / - |
| rag-claude-s1-mixed | cons-hallucination | rag-seed2 | - | - | 0.111 / 0.111 | 2 / 2814 / 403 / - |
| rag-claude-s1-mixed | cons-hallucination | regex-only | 0.626 | 1.000 | 0.222 / 0.222 | 0 / 0 / 0 / 2.645 |
| rag-claude-s1-mixed | inv-datasets | engine-r2 | 0.814 | 1.000 | 0.500 / 1.000 / 0.667 | 114 / 49863 / 3971 / 48.962 |
| rag-claude-s1-mixed | inv-datasets | llm-only | 1.000 | 1.000 | 1.000 / 1.000 / 1.000 | 50 / 49263 / 3978 / 45.071 |
| rag-claude-s1-mixed | inv-datasets | rag-oracle | - | - | 1.000 / 1.000 / 1.000 | 2 / 11353 / 1142 / - |
| rag-claude-s1-mixed | inv-datasets | rag-per-paper | - | - | 1.000 / 1.000 / 1.000 | 2 / 11682 / 1263 / - |
| rag-claude-s1-mixed | inv-datasets | rag-seed1 | - | - | 1.000 / 0.556 / 0.714 | 2 / 3190 / 419 / - |
| rag-claude-s1-mixed | inv-datasets | rag-seed2 | - | - | 1.000 / 0.556 / 0.714 | 2 / 3190 / 427 / - |
| rag-claude-s1-mixed | inv-datasets | regex-only | 1.000 | 1.000 | 1.000 / 1.000 / 1.000 | 0 / 0 / 0 / 0.966 |
| rag-claude-s1-mixed | inv-methods | engine-r2 | 0.953 | 0.167 | 0.700 / 1.000 / 0.824 | 43 / 43370 / 5964 / 62.753 |
| rag-claude-s1-mixed | inv-methods | llm-only | 1.000 | 0.033 | 0.467 / 1.000 / 0.636 | 42 / 41960 / 5926 / 62.965 |
| rag-claude-s1-mixed | inv-methods | rag-oracle | - | - | 0.250 / 0.143 / 0.182 | 2 / 12337 / 2574 / - |
| rag-claude-s1-mixed | inv-methods | rag-per-paper | - | - | 0.500 / 0.286 / 0.364 | 2 / 12677 / 2653 / - |
| rag-claude-s1-mixed | inv-methods | rag-seed1 | - | - | 0.333 / 0.214 / 0.261 | 2 / 3242 / 1160 / - |
| rag-claude-s1-mixed | inv-methods | rag-seed2 | - | - | 0.333 / 0.214 / 0.261 | 2 / 3381 / 1324 / - |
| rag-claude-s1-mixed | inv-methods | regex-only | 1.000 | 0.167 | 1.000 / 1.000 / 1.000 | 0 / 0 / 0 / 1.114 |
| rag-claude-s1-mixed | inv-metrics | engine-r2 | 0.615 | 0.750 | 0.333 / 1.000 / 0.500 | 106 / 43956 / 3899 / 53.265 |
| rag-claude-s1-mixed | inv-metrics | llm-only | 0.920 | 0.750 | 1.000 / 1.000 / 1.000 | 44 / 45716 / 4119 / 44.708 |
| rag-claude-s1-mixed | inv-metrics | rag-oracle | - | - | 1.000 / 0.714 / 0.833 | 2 / 11449 / 1662 / - |
| rag-claude-s1-mixed | inv-metrics | rag-per-paper | - | - | 1.000 / 0.714 / 0.833 | 2 / 11014 / 1287 / - |
| rag-claude-s1-mixed | inv-metrics | rag-seed1 | - | - | 0.750 / 0.857 / 0.800 | 2 / 3077 / 635 / - |
| rag-claude-s1-mixed | inv-metrics | rag-seed2 | - | - | 0.750 / 0.857 / 0.800 | 2 / 3077 / 635 / - |
| rag-claude-s1-mixed | inv-metrics | regex-only | 0.885 | 0.625 | 0.667 / 0.857 / 0.750 | 0 / 0 / 0 / 1.428 |
| rag-claude-s1-mixed | rag-factuality | engine-r2 | 0.847 | 0.958 | yes / 0.950 / 0.950 | 66 / 79238 / 12391 / 169.705 |
| rag-claude-s1-mixed | rag-factuality | llm-only | 0.933 | 0.955 | yes / 0.800 / 0.800 | 129 / 150395 / 28305 / 307.529 |
| rag-claude-s1-mixed | rag-factuality | rag-oracle | - | - | yes / 0.750 / 0.850 | 2 / 11780 / 3426 / - |
| rag-claude-s1-mixed | rag-factuality | rag-per-paper | - | - | yes / 0.700 / 1.000 | 2 / 12784 / 4187 / - |
| rag-claude-s1-mixed | rag-factuality | rag-seed1 | - | - | yes / 0.200 / 0.250 | 2 / 3128 / 1468 / - |
| rag-claude-s1-mixed | rag-factuality | rag-seed2 | - | - | yes / 0.200 / 0.250 | 2 / 3128 / 1468 / - |
| rag-claude-s1-mixed | rag-factuality | regex-only | 0.626 | 1.000 | yes / 0.250 / 0.250 | 0 / 0 / 0 / 2.273 |
| rag-claude-s1-mixed | rag-hallucination | engine-r2 | 0.640 | 0.325 | no / 0.667 / 0.667 | 143 / 64946 / 7230 / 82.955 |
| rag-claude-s1-mixed | rag-hallucination | llm-only | 0.933 | 0.955 | no / 0.556 / 0.556 | 129 / 150595 / 28299 / 327.758 |
| rag-claude-s1-mixed | rag-hallucination | rag-oracle | - | - | yes / 0.889 / 0.889 | 2 / 11859 / 1692 / - |
| rag-claude-s1-mixed | rag-hallucination | rag-per-paper | - | - | yes / 0.889 / 1.000 | 2 / 12437 / 1906 / - |
| rag-claude-s1-mixed | rag-hallucination | rag-seed1 | - | - | no / 0.444 / 0.556 | 2 / 3093 / 499 / - |
| rag-claude-s1-mixed | rag-hallucination | rag-seed2 | - | - | no / 0.444 / 0.556 | 2 / 3093 / 499 / - |
| rag-claude-s1-mixed | rag-hallucination | regex-only | 0.626 | 1.000 | no / 0.222 / 0.222 | 0 / 0 / 0 / 2.585 |
| rag-claude-s1-mixed | rag-latency | engine-r2 | 0.626 | 0.796 | yes / 1.000 / 1.000 | 148 / 63014 / 6913 / 95.209 |
| rag-claude-s1-mixed | rag-latency | llm-only | 0.920 | 0.954 | yes / 1.000 / 1.000 | 111 / 131973 / 26168 / 283.698 |
| rag-claude-s1-mixed | rag-latency | rag-oracle | - | - | yes / 0.333 / 1.000 | 2 / 11443 / 930 / - |
| rag-claude-s1-mixed | rag-latency | rag-per-paper | - | - | yes / 0.000 / 0.667 | 2 / 11565 / 579 / - |
| rag-claude-s1-mixed | rag-latency | rag-seed1 | - | - | no / 0.000 / 0.333 | 2 / 3086 / 280 / - |
| rag-claude-s1-mixed | rag-latency | rag-seed2 | - | - | no / 0.000 / 0.333 | 2 / 3086 / 280 / - |
| rag-claude-s1-mixed | rag-latency | regex-only | 0.570 | 1.000 | no / 0.333 / 0.333 | 0 / 0 / 0 / 2.285 |
| rag-tpl-hard-complex | best-accuracy | rag-per-paper-k1 | - | - | no / 0.000 / 0.000 | 2 / 28899 / 923 / - |
| rag-tpl-hard-complex | best-hallucination | rag-per-paper-k1 | - | - | no / 0.000 / 0.000 | 2 / 27976 / 485 / - |
| rag-tpl-hard-complex | cons-accuracy | rag-per-paper-k1 | - | - | 0.077 / 0.103 | 2 / 34754 / 922 / - |
| rag-tpl-hard-complex | cons-hallucination | rag-per-paper-k1 | - | - | 0.054 / 0.054 | 2 / 60686 / 8288 / - |
| rag-tpl-hard-complex | inv-datasets | rag-per-paper-k1 | - | - | MISSING | - |
| rag-tpl-hard-complex | inv-methods | rag-per-paper-k1 | - | - | MISSING | - |
| rag-tpl-hard-complex | inv-metrics | rag-per-paper-k1 | - | - | MISSING | - |
| rag-tpl-hard-complex | rag-factuality | rag-per-paper-k1 | - | - | yes / 0.390 / 0.400 | 2 / 30764 / 6066 / - |
| rag-tpl-hard-complex | rag-hallucination | rag-per-paper-k1 | - | - | yes / 0.119 / 0.119 | 2 / 28832 / 1056 / - |
| rag-tpl-hard-complex | rag-latency | rag-per-paper-k1 | - | - | yes / 0.154 / 0.231 | 2 / 24740 / 2436 / - |

## Repeat spread

C ranges include the original run and available valid repeats. Engine repeats with failed service calls are excluded. Differences smaller than the observed spread are not evidence of a difference between systems.

| question | system | C metric | samples | min | max | range |
|---|---|---|---|---|---|---|
| rag-factuality | rag-baseline | label_correct | 3 | 1.000 | 1.000 | 0.000 |
| rag-factuality | rag-baseline | direction_accuracy | 3 | 0.050 | 0.200 | 0.150 |
| rag-factuality | rag-baseline | completeness | 3 | 0.250 | 0.250 | 0.000 |
| rag-factuality | evidence-engine | label_correct | 2 | 1.000 | 1.000 | 0.000 |
| rag-factuality | evidence-engine | direction_accuracy | 2 | 0.950 | 0.950 | 0.000 |
| rag-factuality | evidence-engine | completeness | 2 | 0.950 | 0.950 | 0.000 |
| rag-hallucination | rag-baseline | label_correct | 3 | 0.000 | 0.000 | 0.000 |
| rag-hallucination | rag-baseline | direction_accuracy | 3 | 0.444 | 0.444 | 0.000 |
| rag-hallucination | rag-baseline | completeness | 3 | 0.556 | 0.556 | 0.000 |
| rag-hallucination | evidence-engine | label_correct | 2 | 0.000 | 0.000 | 0.000 |
| rag-hallucination | evidence-engine | direction_accuracy | 2 | 0.667 | 0.667 | 0.000 |
| rag-hallucination | evidence-engine | completeness | 2 | 0.667 | 0.667 | 0.000 |
| rag-latency | rag-baseline | label_correct | 3 | 0.000 | 0.000 | 0.000 |
| rag-latency | rag-baseline | direction_accuracy | 3 | 0.000 | 0.000 | 0.000 |
| rag-latency | rag-baseline | completeness | 3 | 0.333 | 0.333 | 0.000 |
| rag-latency | evidence-engine | label_correct | 2 | 1.000 | 1.000 | 0.000 |
| rag-latency | evidence-engine | direction_accuracy | 2 | 1.000 | 1.000 | 0.000 |
| rag-latency | evidence-engine | completeness | 2 | 1.000 | 1.000 | 0.000 |
| inv-metrics | rag-baseline | precision | 3 | 0.750 | 0.750 | 0.000 |
| inv-metrics | rag-baseline | recall | 3 | 0.857 | 0.857 | 0.000 |
| inv-metrics | rag-baseline | f1 | 3 | 0.800 | 0.800 | 0.000 |
| inv-metrics | evidence-engine | precision | 2 | 0.333 | 0.333 | 0.000 |
| inv-metrics | evidence-engine | recall | 2 | 1.000 | 1.000 | 0.000 |
| inv-metrics | evidence-engine | f1 | 2 | 0.500 | 0.500 | 0.000 |
| inv-methods | rag-baseline | precision | 3 | 0.333 | 0.333 | 0.000 |
| inv-methods | rag-baseline | recall | 3 | 0.214 | 0.214 | 0.000 |
| inv-methods | rag-baseline | f1 | 3 | 0.261 | 0.261 | 0.000 |
| inv-methods | evidence-engine | precision | 2 | 0.700 | 0.700 | 0.000 |
| inv-methods | evidence-engine | recall | 2 | 1.000 | 1.000 | 0.000 |
| inv-methods | evidence-engine | f1 | 2 | 0.824 | 0.824 | 0.000 |
| inv-datasets | rag-baseline | precision | 3 | 1.000 | 1.000 | 0.000 |
| inv-datasets | rag-baseline | recall | 3 | 0.556 | 0.556 | 0.000 |
| inv-datasets | rag-baseline | f1 | 3 | 0.714 | 0.714 | 0.000 |
| inv-datasets | evidence-engine | precision | 2 | 0.500 | 0.500 | 0.000 |
| inv-datasets | evidence-engine | recall | 2 | 1.000 | 1.000 | 0.000 |
| inv-datasets | evidence-engine | f1 | 2 | 0.667 | 0.667 | 0.000 |
| cons-accuracy | rag-baseline | per_study_accuracy | 3 | 0.000 | 0.182 | 0.182 |
| cons-accuracy | rag-baseline | completeness | 3 | 0.091 | 0.273 | 0.182 |
| cons-accuracy | evidence-engine | per_study_accuracy | 2 | 0.909 | 0.909 | 0.000 |
| cons-accuracy | evidence-engine | completeness | 2 | 0.909 | 0.909 | 0.000 |
| cons-hallucination | rag-baseline | per_study_accuracy | 3 | 0.111 | 0.111 | 0.000 |
| cons-hallucination | rag-baseline | completeness | 3 | 0.111 | 0.111 | 0.000 |
| cons-hallucination | evidence-engine | per_study_accuracy | 2 | 0.667 | 0.667 | 0.000 |
| cons-hallucination | evidence-engine | completeness | 2 | 0.667 | 0.667 | 0.000 |
| best-accuracy | rag-baseline | winner_correct | 3 | 0.000 | 0.000 | 0.000 |
| best-accuracy | rag-baseline | per_study_accuracy | 3 | 0.091 | 0.091 | 0.000 |
| best-accuracy | rag-baseline | completeness | 3 | 0.091 | 0.182 | 0.091 |
| best-accuracy | evidence-engine | winner_correct | 2 | 1.000 | 1.000 | 0.000 |
| best-accuracy | evidence-engine | per_study_accuracy | 2 | 0.909 | 0.909 | 0.000 |
| best-accuracy | evidence-engine | completeness | 2 | 1.000 | 1.000 | 0.000 |
| best-hallucination | rag-baseline | winner_correct | 3 | 0.000 | 1.000 | 1.000 |
| best-hallucination | rag-baseline | per_study_accuracy | 3 | 0.333 | 0.556 | 0.222 |
| best-hallucination | rag-baseline | completeness | 3 | 0.333 | 0.556 | 0.222 |
| best-hallucination | evidence-engine | winner_correct | 2 | 1.000 | 1.000 | 0.000 |
| best-hallucination | evidence-engine | per_study_accuracy | 2 | 0.667 | 0.667 | 0.000 |
| best-hallucination | evidence-engine | completeness | 2 | 0.667 | 0.667 | 0.000 |

## Counterfactual

wrote /mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-qf/scores/shift-cf-S001/shift.json and /mnt/ceph/storage/data-tmp/2026/xepi3167/evidence-qf/scores/shift-cf-S001/shift.md: shifted as expected: evidence-engine=yes, rag-baseline=no, agent-baseline=yes

# Shift from rag-claude-s1-ec928480 to rag-claude-s1-cf-5893772b

Study S001 (paper S001): supports -> contradicts; changed measurements: S001.m1: 0.295 -> 0.168, S001.m2: 0.178 -> 0.202, S001.m9: 0.316 -> 0.229, S001.m10: 0.194 -> 0.285.
Expected label: mixed -> mixed (does not change).

## The changed study's direction

| system          | from     | before       | before_correct   | to          | after        | after_correct   |
|-----------------|----------|--------------|------------------|-------------|--------------|-----------------|
| evidence-engine | supports | supports     | yes              | contradicts | contradicts  | yes             |
| rag-baseline    | supports | undetermined | no               | contradicts | undetermined | no              |
| agent-baseline  | supports | supports     | yes              | contradicts | contradicts  | yes             |

## The label

| system          | expected_before   | before   | before_correct   | expected_after   | after   | after_correct   | changed   | shifted_as_expected   |
|-----------------|-------------------|----------|------------------|------------------|---------|-----------------|-----------|-----------------------|
| evidence-engine | mixed             | mixed    | yes              | mixed            | mixed   | yes             | no        | yes                   |
| rag-baseline    | mixed             | mixed    | yes              | mixed            | mixed   | yes             | no        | no                    |
| agent-baseline  | mixed             | mixed    | yes              | mixed            | mixed   | yes             | no        | yes                   |

shifted_as_expected: the direction before and after and the label before and after are all as predicted.


## Cache preservation

The verified 15 MB cache archive is split into reports/question-first/caches.tar.gz.part-aa; join with cat caches.tar.gz.part-* > caches.tar.gz.

## Limits

1. All numbers come from two synthetic corpora on one topic, made with a fixed vocabulary that the extractors and
   protocols were also written against; extraction scores are an upper bound.
2. The main corpus has 20 papers; some cells rest on 3-11 papers, so differences under about 0.3 are not shown.
3. The over-claiming test rests on 4 papers (the hard corpus has none), so it is a demonstration, not a measurement.
4. All systems use the same local model; the grid's RAG baseline reads 8 passages, so the per-paper RAG row and
   the cost column separate "reads more" from "reasons from evidence".
5. Truth and engine share the synthesis rules, so C tests extraction and pairing; the oracle row shows the ceiling
   and the counterfactual shows whether the answer follows the evidence.
6. The baselines are not told the protocol's neutral band (`min_effect`: 0.01, 0.05 s for latency) or its metric
   definitions; a baseline that calls a change inside the band "better" or "worse" is scored wrong for a rule it
   never saw.

| cell | n | what it means |
|---|---|---|
| rag-latency, main, C `direction_accuracy` | 3 decidable papers | one paper moves it by 0.33 |
| every effect question, both corpora, C `label_correct` | 1 label, truth `mixed` in all 6 cells | "always say mixed" scores 6/6 |
| cons-accuracy / cons-hallucination, hard | 0 disagreeing papers | "always agrees" scores 1.0 |
| cons-accuracy / cons-hallucination, main | 3 / 1 disagreeing papers | the over-claiming test, 4 papers |
| per level, main | 4 papers per level | describe only, no comparison |
