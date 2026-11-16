# Backend status by week, before and after the reruns

A week counts as model work only when at least one domain model completed. `recorded ok` is what `runs.json` says, which overstates success for the zero-scenario runs. Reruns and added backends used later code and settings, so they are not like-for-like with the original batch. Retired models could not be rerun because the provider no longer serves them.

| backend | group | first batch: recorded ok | first batch: model work | first batch: clean | weeks rerun | now: model work | now: clean | models completed per working week |
|---|---|---|---|---|---|---|---|---|
| anthropic-opus-4-8 | original | 0/8 | 0/8 | 0/8 | 8 | 6/8 | 6/8 | 90 |
| anthropic-sonnet-4-6 | original | 8/8 | 3/8 | 3/8 | 5 | 8/8 | 8/8 | 48, 90 |
| groq-gpt-oss-120b | original | 6/8 | 6/8 | 5/8 | 2 | 8/8 | 7/8 | 48, 90 |
| groq-gpt-oss-20b | original | 6/8 | 6/8 | 0/8 | 2 | 7/8 | 0/8 | 43, 48, 90 |
| groq-llama-3.1-8b (retired) | original | 0/8 | 0/8 | 0/8 | 0 | 0/8 | 0/8 | - |
| groq-llama-3.3-70b (retired) | original | 0/8 | 0/8 | 0/8 | 0 | 0/8 | 0/8 | - |
| groq-llama4-scout (retired) | original | 7/8 | 7/8 | 6/8 | 0 | 7/8 | 6/8 | 42, 45, 48 |
| groq-qwen3-32b (retired) | original | 0/8 | 0/8 | 0/8 | 0 | 0/8 | 0/8 | - |
| anthropic-haiku-4-5 | added | 1/8 | 1/8 | 1/8 | 0 | 1/8 | 1/8 | 90 |
| groq-qwen3.6-27b | added | 1/8 | 1/8 | 1/8 | 0 | 1/8 | 1/8 | 81 |
| groq-qwen3.8-27b | added | 8/8 | 8/8 | 0/8 | 0 | 8/8 | 0/8 | 6, 12, 14, 15, 17, 19, 24, 27 |

## Current result per week

`W` model work and clean synthesis, `w` model work with failed synthesis sections, `-` no model work.

| backend | 2026-02-15 | 2026-02-22 | 2026-03-01 | 2026-03-08 | 2026-03-15 | 2026-03-22 | 2026-03-29 | 2026-04-05 |
|---|---|---|---|---|---|---|---|---|
| anthropic-opus-4-8 | W | - | W | W | W | W | - | W |
| anthropic-sonnet-4-6 | W | W | W | W | W | W | W | W |
| groq-gpt-oss-120b | w | W | W | W | W | W | W | W |
| groq-gpt-oss-20b | w | w | - | w | w | w | w | w |
| groq-llama-3.1-8b | - | - | - | - | - | - | - | - |
| groq-llama-3.3-70b | - | - | - | - | - | - | - | - |
| groq-llama4-scout | W | w | W | W | W | - | W | W |
| groq-qwen3-32b | - | - | - | - | - | - | - | - |
| anthropic-haiku-4-5 | W | - | - | - | - | - | - | - |
| groq-qwen3.6-27b | - | - | - | - | - | W | - | - |
| groq-qwen3.8-27b | w | w | w | w | w | w | w | w |
