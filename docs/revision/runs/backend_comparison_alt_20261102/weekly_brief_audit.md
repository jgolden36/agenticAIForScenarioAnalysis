# Numeric audit of weekly briefs

A match means the number appears somewhere in that week's fetched text, so these rates are an upper bound on support. A miss is not proof of fabrication, since fetched text may be truncated.

| backend | briefs | numbers | found in sources | rate | substantive numbers | found | rate |
|---|---|---|---|---|---|---|---|
| anthropic-haiku-4-5 | 1 | 22 | 22 | 1.0 | 15 | 15 | 1.0 |
| groq-qwen3.6-27b | 8 | 462 | 450 | 0.974 | 248 | 236 | 0.9516 |
| groq-qwen3.8-27b | 8 | 31 | 31 | 1.0 | 12 | 12 | 1.0 |

Every number with its context, for review: `weekly_brief_audit_tokens.csv`.
