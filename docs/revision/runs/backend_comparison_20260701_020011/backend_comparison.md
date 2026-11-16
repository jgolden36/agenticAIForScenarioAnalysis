# LLM backend comparison

Clean synthesis definition: A run has a clean synthesis when (1) the Module 4 synthesis state was written, (2) every (scenario, section) LLM call completed without an unrecoverable error (context_budget_summary.sections_failed == 0), (3) no bash-layer failure was recorded for the synthesis stage, and (4) every scenario in the run has at least one completed model and at least one synthesized outcome.

Denominator: `cells_attempted` is the number of (scenario, model) parameter sets Module 2 produced for the run (or Module 3 records when parameter records are unavailable); `grid_cells` is scenarios x model specs. Wall-clock excludes analyst review (auto-approved in batch mode).

## Per backend

| backend | runs | clean weeks | clean rate | completed per week | mean completed | model span s per week | mean span s |
|---|---|---|---|---|---|---|---|
| anthropic-sonnet-4-6 | 8 | cmp_20260701_020011_anthropic-sonnet-4-6_20260215, cmp_20260701_020011_anthropic-sonnet-4-6_20260322, cmp_20260701_020011_anthropic-sonnet-4-6_20260405 | 0.375 | 48, 0, 0, 0, 0, 48, 0, 48 | 18 | 45.396, 44.585, 44.618 | 44.9 |
| groq-gpt-oss-120b | 6 | cmp_20260701_020011_groq-gpt-oss-120b_20260222, cmp_20260701_020011_groq-gpt-oss-120b_20260301, cmp_20260701_020011_groq-gpt-oss-120b_20260308, cmp_20260701_020011_groq-gpt-oss-120b_20260315, cmp_20260701_020011_groq-gpt-oss-120b_20260322 | 0.833 | 48, 48, 48, 48, 48, 48 | 48 | 45.176, 44.993, 44.131, 44.866, 43.881, 45.238 | 44.7 |
| groq-gpt-oss-20b | 6 | - | 0.0 | 48, 48, 48, 48, 43, 48 | 47.17 | 44.874, 44.823, 44.55, 44.576, 43.752, 44.754 | 44.6 |
| groq-llama4-scout | 7 | cmp_20260701_020011_groq-llama4-scout_20260215, cmp_20260701_020011_groq-llama4-scout_20260301, cmp_20260701_020011_groq-llama4-scout_20260308, cmp_20260701_020011_groq-llama4-scout_20260315, cmp_20260701_020011_groq-llama4-scout_20260329, cmp_20260701_020011_groq-llama4-scout_20260405 | 0.857 | 48, 48, 42, 45, 48, 42, 42 | 45 | 44.844, 45.126, 42.586, 42.804, 44.514, 43.88, 41.359 | 43.6 |

## Backends with no clean week

| backend | runs | principal failure reasons |
|---|---|---|
| groq-gpt-oss-20b | 6 | BadRequestError: 4; BadRequestError: 5; BadRequestError: 8; BadRequestError: 9 |

## Per run

| backend | week | attempted | completed | failed | skipped | outcomes | sections failed | clean | model span s | s per completed model |
|---|---|---|---|---|---|---|---|---|---|---|
| anthropic-sonnet-4-6 | cmp_20260701_020011_anthropic-sonnet-4-6_20260215 | 170 | 48 | 14 | 38 | 313 | 0 | True | 45.396 | 0.8097 |
| anthropic-sonnet-4-6 | cmp_20260701_020011_anthropic-sonnet-4-6_20260222 | 0 | 0 | 0 | 0 | 0 | 0 | False | None | None |
| anthropic-sonnet-4-6 | cmp_20260701_020011_anthropic-sonnet-4-6_20260301 | 0 | 0 | 0 | 0 | 0 | 0 | False | None | None |
| anthropic-sonnet-4-6 | cmp_20260701_020011_anthropic-sonnet-4-6_20260308 | 0 | 0 | 0 | 0 | 0 | 0 | False | None | None |
| anthropic-sonnet-4-6 | cmp_20260701_020011_anthropic-sonnet-4-6_20260315 | 0 | 0 | 0 | 0 | 0 | 0 | False | None | None |
| anthropic-sonnet-4-6 | cmp_20260701_020011_anthropic-sonnet-4-6_20260322 | 170 | 48 | 14 | 38 | 324 | 0 | True | 44.585 | 0.7544 |
| anthropic-sonnet-4-6 | cmp_20260701_020011_anthropic-sonnet-4-6_20260329 | 0 | 0 | 0 | 0 | 0 | 0 | False | None | None |
| anthropic-sonnet-4-6 | cmp_20260701_020011_anthropic-sonnet-4-6_20260405 | 170 | 48 | 14 | 38 | 323 | 0 | True | 44.618 | 0.752 |
| groq-gpt-oss-120b | cmp_20260701_020011_groq-gpt-oss-120b_20260215 | 170 | 48 | 15 | 37 | 680 | 1 | False | 45.176 | 0.7671 |
| groq-gpt-oss-120b | cmp_20260701_020011_groq-gpt-oss-120b_20260222 | 170 | 48 | 15 | 37 | 709 | 0 | True | 44.993 | 0.7514 |
| groq-gpt-oss-120b | cmp_20260701_020011_groq-gpt-oss-120b_20260301 | 170 | 48 | 16 | 36 | 680 | 0 | True | 44.131 | 0.7556 |
| groq-gpt-oss-120b | cmp_20260701_020011_groq-gpt-oss-120b_20260308 | 170 | 48 | 16 | 36 | 642 | 0 | True | 44.866 | 0.7601 |
| groq-gpt-oss-120b | cmp_20260701_020011_groq-gpt-oss-120b_20260315 | 170 | 48 | 14 | 38 | 611 | 0 | True | 43.881 | 0.7481 |
| groq-gpt-oss-120b | cmp_20260701_020011_groq-gpt-oss-120b_20260322 | 170 | 48 | 15 | 37 | 677 | 0 | True | 45.238 | 0.7634 |
| groq-gpt-oss-20b | cmp_20260701_020011_groq-gpt-oss-20b_20260215 | 170 | 48 | 16 | 36 | 497 | 9 | False | 44.874 | 0.7625 |
| groq-gpt-oss-20b | cmp_20260701_020011_groq-gpt-oss-20b_20260222 | 170 | 48 | 14 | 38 | 428 | 8 | False | 44.823 | 0.756 |
| groq-gpt-oss-20b | cmp_20260701_020011_groq-gpt-oss-20b_20260315 | 170 | 48 | 15 | 37 | 536 | 5 | False | 44.55 | 0.7601 |
| groq-gpt-oss-20b | cmp_20260701_020011_groq-gpt-oss-20b_20260322 | 170 | 48 | 15 | 37 | 641 | 4 | False | 44.576 | 0.7607 |
| groq-gpt-oss-20b | cmp_20260701_020011_groq-gpt-oss-20b_20260329 | 170 | 43 | 20 | 37 | 462 | 5 | False | 43.752 | 0.7042 |
| groq-gpt-oss-20b | cmp_20260701_020011_groq-gpt-oss-20b_20260405 | 170 | 48 | 14 | 38 | 612 | 4 | False | 44.754 | 0.7521 |
| groq-llama4-scout | cmp_20260701_020011_groq-llama4-scout_20260215 | 170 | 48 | 14 | 38 | 146 | 0 | True | 44.844 | 0.7554 |
| groq-llama4-scout | cmp_20260701_020011_groq-llama4-scout_20260222 | 170 | 48 | 14 | 38 | 124 | 2 | False | 45.126 | 0.7629 |
| groq-llama4-scout | cmp_20260701_020011_groq-llama4-scout_20260301 | 170 | 42 | 20 | 38 | 137 | 0 | True | 42.586 | 0.5808 |
| groq-llama4-scout | cmp_20260701_020011_groq-llama4-scout_20260308 | 170 | 45 | 17 | 38 | 130 | 0 | True | 42.804 | 0.6646 |
| groq-llama4-scout | cmp_20260701_020011_groq-llama4-scout_20260315 | 170 | 48 | 14 | 38 | 158 | 0 | True | 44.514 | 0.7609 |
| groq-llama4-scout | cmp_20260701_020011_groq-llama4-scout_20260329 | 169 | 42 | 21 | 37 | 130 | 0 | True | 43.88 | 0.566 |
| groq-llama4-scout | cmp_20260701_020011_groq-llama4-scout_20260405 | 170 | 42 | 20 | 38 | 145 | 0 | True | 41.359 | 0.5931 |
