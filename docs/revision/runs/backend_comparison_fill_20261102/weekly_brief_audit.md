# Numeric audit of weekly briefs

A match means the number appears somewhere in that week's fetched text, so these rates are an upper bound on support. A miss is not proof of fabrication, since fetched text may be truncated.

| backend | briefs | numbers | found in sources | rate | substantive numbers | found | rate |
|---|---|---|---|---|---|---|---|
| anthropic-opus-4-8 | 8 | 289 | 277 | 0.9585 | 182 | 170 | 0.9341 |
| groq-gpt-oss-120b | 2 | 45 | 43 | 0.9556 | 37 | 35 | 0.9459 |
| groq-gpt-oss-20b | 1 | 3 | 3 | 1.0 | 1 | 1 | 1.0 |

Every number with its context, for review: `weekly_brief_audit_tokens.csv`.
