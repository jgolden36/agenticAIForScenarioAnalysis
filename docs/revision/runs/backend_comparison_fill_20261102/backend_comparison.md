# LLM backend comparison

Clean synthesis definition: A run has a clean synthesis when (1) the Module 4 synthesis state was written, (2) every (scenario, section) LLM call completed without an unrecoverable error (context_budget_summary.sections_failed == 0), (3) no bash-layer failure was recorded for the synthesis stage, and (4) every scenario in the run has at least one completed model and at least one synthesized outcome.

Denominator: `cells_attempted` is the number of (scenario, model) parameter sets Module 2 produced for the run (or Module 3 records when parameter records are unavailable); `grid_cells` is scenarios x model specs. Wall-clock excludes analyst review (auto-approved in batch mode).

## Per backend

| backend | runs | clean weeks | clean rate | completed per week | mean completed | model span s per week | mean span s |
|---|---|---|---|---|---|---|---|
| anthropic-opus-4-8 | 6 | cmp_fill_20261102_anthropic-opus-4-8_20260215, cmp_fill_20261102_anthropic-opus-4-8_20260301, cmp_fill_20261102_anthropic-opus-4-8_20260308, cmp_fill_20261102_anthropic-opus-4-8_20260315, cmp_fill_20261102_anthropic-opus-4-8_20260322, cmp_fill_20261102_anthropic-opus-4-8_20260405 | 1.0 | 90, 90, 90, 90, 90, 90 | 90 | 26.878, 37.257, 41.212, 40.598, 40.289, 40.624 | 37.8 |
| anthropic-sonnet-4-6 | 5 | cmp_fill_20261102_anthropic-sonnet-4-6_20260222, cmp_fill_20261102_anthropic-sonnet-4-6_20260301, cmp_fill_20261102_anthropic-sonnet-4-6_20260308, cmp_fill_20261102_anthropic-sonnet-4-6_20260315, cmp_fill_20261102_anthropic-sonnet-4-6_20260329 | 1.0 | 90, 90, 90, 90, 90 | 90 | 49.161, 51.526, 48.622, 43.552, 42.342 | 47.0 |
| groq-gpt-oss-120b | 2 | cmp_fill_20261102_groq-gpt-oss-120b_20260329, cmp_fill_20261102_groq-gpt-oss-120b_20260405 | 1.0 | 90, 90 | 90 | 28.579, 29.342 | 29.0 |
| groq-gpt-oss-20b | 1 | - | 0.0 | 90 | 90 | 26.945 | 26.9 |

## Backends with no clean week

| backend | runs | principal failure reasons |
|---|---|---|
| groq-gpt-oss-20b | 1 | BadRequestError: 8 |

## Per run

| backend | week | attempted | completed | failed | skipped | outcomes | sections failed | clean | model span s | s per completed model |
|---|---|---|---|---|---|---|---|---|---|---|
| anthropic-opus-4-8 | cmp_fill_20261102_anthropic-opus-4-8_20260215 | 170 | 90 | 31 | 49 | 242 | 0 | True | 26.878 | 0.4222 |
| anthropic-opus-4-8 | cmp_fill_20261102_anthropic-opus-4-8_20260301 | 170 | 90 | 31 | 49 | 226 | 0 | True | 37.257 | 0.4553 |
| anthropic-opus-4-8 | cmp_fill_20261102_anthropic-opus-4-8_20260308 | 170 | 90 | 30 | 50 | 261 | 0 | True | 41.212 | 0.5038 |
| anthropic-opus-4-8 | cmp_fill_20261102_anthropic-opus-4-8_20260315 | 170 | 90 | 31 | 49 | 229 | 0 | True | 40.598 | 0.4815 |
| anthropic-opus-4-8 | cmp_fill_20261102_anthropic-opus-4-8_20260322 | 170 | 90 | 29 | 51 | 236 | 0 | True | 40.289 | 0.4865 |
| anthropic-opus-4-8 | cmp_fill_20261102_anthropic-opus-4-8_20260405 | 170 | 90 | 30 | 50 | 225 | 0 | True | 40.624 | 0.5117 |
| anthropic-sonnet-4-6 | cmp_fill_20261102_anthropic-sonnet-4-6_20260222 | 170 | 90 | 26 | 54 | 508 | 0 | True | 49.161 | 0.7949 |
| anthropic-sonnet-4-6 | cmp_fill_20261102_anthropic-sonnet-4-6_20260301 | 170 | 90 | 26 | 54 | 472 | 0 | True | 51.526 | 0.7861 |
| anthropic-sonnet-4-6 | cmp_fill_20261102_anthropic-sonnet-4-6_20260308 | 170 | 90 | 26 | 54 | 459 | 0 | True | 48.622 | 0.7588 |
| anthropic-sonnet-4-6 | cmp_fill_20261102_anthropic-sonnet-4-6_20260315 | 170 | 90 | 26 | 54 | 478 | 0 | True | 43.552 | 0.6897 |
| anthropic-sonnet-4-6 | cmp_fill_20261102_anthropic-sonnet-4-6_20260329 | 170 | 90 | 26 | 54 | 477 | 0 | True | 42.342 | 0.6827 |
| groq-gpt-oss-120b | cmp_fill_20261102_groq-gpt-oss-120b_20260329 | 170 | 90 | 28 | 50 | 862 | 0 | True | 28.579 | 0.5275 |
| groq-gpt-oss-120b | cmp_fill_20261102_groq-gpt-oss-120b_20260405 | 170 | 90 | 29 | 50 | 840 | 0 | True | 29.342 | 0.4705 |
| groq-gpt-oss-20b | cmp_fill_20261102_groq-gpt-oss-20b_20260308 | 170 | 90 | 27 | 51 | 659 | 8 | False | 26.945 | 0.4282 |
