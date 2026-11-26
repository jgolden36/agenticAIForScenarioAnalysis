# Numeric audit of weekly briefs

A match means the number appears somewhere in that week's fetched text, so these rates are an upper bound on support. A miss is not proof of fabrication, since fetched text may be truncated.

| backend | briefs | numbers | found in sources | rate | substantive numbers | found | rate |
|---|---|---|---|---|---|---|---|
| anthropic-sonnet-4-6 | 8 | 394 | 386 | 0.9797 | 219 | 211 | 0.9635 |
| groq-gpt-oss-120b | 6 | 141 | 139 | 0.9858 | 97 | 95 | 0.9794 |
| groq-gpt-oss-20b | 6 | 86 | 85 | 0.9884 | 60 | 59 | 0.9833 |
| groq-llama4-scout | 7 | 54 | 54 | 1.0 | 41 | 41 | 1.0 |

Every number with its context, for review: `weekly_brief_audit_tokens.csv`.
