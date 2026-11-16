# LLM backend comparison

Clean synthesis definition: A run has a clean synthesis when (1) the Module 4 synthesis state was written, (2) every (scenario, section) LLM call completed without an unrecoverable error (context_budget_summary.sections_failed == 0), (3) no bash-layer failure was recorded for the synthesis stage, and (4) every scenario in the run has at least one completed model and at least one synthesized outcome.

Denominator: `cells_attempted` is the number of (scenario, model) parameter sets Module 2 produced for the run (or Module 3 records when parameter records are unavailable); `grid_cells` is scenarios x model specs. Wall-clock excludes analyst review (auto-approved in batch mode).

## Per backend

| backend | runs | clean weeks | clean rate | completed per week | mean completed | model span s per week | mean span s |
|---|---|---|---|---|---|---|---|
| anthropic-haiku-4-5 | 1 | cmp_alt_20261102_anthropic-haiku-4-5_20260215 | 1.0 | 90 | 90 | 40.778 | 40.8 |
| groq-qwen3.6-27b | 1 | cmp_alt_20261102_groq-qwen3.6-27b_20260322 | 1.0 | 81 | 81 | 33.985 | 34.0 |
| groq-qwen3.8-27b | 8 | - | 0.0 | 17, 24, 19, 15, 27, 12, 6, 14 | 16.75 | 6.823, 7.873, 5.192, 6.062, 8.018, 4.598, 4.421, 5.496 | 6.1 |

## Backends with no clean week

| backend | runs | principal failure reasons |
|---|---|---|
| groq-qwen3.8-27b | 8 | no synthesis state / no outcomes |

## Per run

| backend | week | attempted | completed | failed | skipped | outcomes | sections failed | clean | model span s | s per completed model |
|---|---|---|---|---|---|---|---|---|---|---|
| anthropic-haiku-4-5 | cmp_alt_20261102_anthropic-haiku-4-5_20260215 | 170 | 90 | 31 | 49 | 893 | 0 | True | 40.778 | 0.4991 |
| groq-qwen3.6-27b | cmp_alt_20261102_groq-qwen3.6-27b_20260322 | 170 | 81 | 23 | 47 | 361 | 0 | True | 33.985 | 0.506 |
| groq-qwen3.8-27b | cmp_alt_20261102_groq-qwen3.8-27b_20260215 | 170 | 17 | 2 | 9 | 0 | 0 | False | 6.823 | 0.0041 |
| groq-qwen3.8-27b | cmp_alt_20261102_groq-qwen3.8-27b_20260222 | 170 | 24 | 4 | 8 | 0 | 0 | False | 7.873 | 0.0035 |
| groq-qwen3.8-27b | cmp_alt_20261102_groq-qwen3.8-27b_20260301 | 170 | 19 | 0 | 3 | 0 | 0 | False | 5.192 | 0.0037 |
| groq-qwen3.8-27b | cmp_alt_20261102_groq-qwen3.8-27b_20260308 | 170 | 15 | 3 | 5 | 0 | 0 | False | 6.062 | 0.0045 |
| groq-qwen3.8-27b | cmp_alt_20261102_groq-qwen3.8-27b_20260315 | 170 | 27 | 2 | 6 | 0 | 0 | False | 8.018 | 0.0034 |
| groq-qwen3.8-27b | cmp_alt_20261102_groq-qwen3.8-27b_20260322 | 170 | 12 | 1 | 2 | 0 | 0 | False | 4.598 | 0.0032 |
| groq-qwen3.8-27b | cmp_alt_20261102_groq-qwen3.8-27b_20260329 | 170 | 6 | 1 | 6 | 0 | 0 | False | 4.421 | 0.0047 |
| groq-qwen3.8-27b | cmp_alt_20261102_groq-qwen3.8-27b_20260405 | 170 | 14 | 1 | 1 | 0 | 0 | False | 5.496 | 0.0032 |
