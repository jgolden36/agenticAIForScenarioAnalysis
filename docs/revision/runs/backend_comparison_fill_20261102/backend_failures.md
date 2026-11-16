# Backend failures in batch `fill_20261102`

3 runs failed at the weekly brief or at scenario generation, before any domain model ran.

| backend | model | runs | ok | failed at brief | failed at scenarios | principal error |
|---|---|---|---|---|---|---|
| anthropic-opus-4-8 | claude-opus-4-8 | 8 | 6 | 0 | 2 | scenario_schema_validation (2) |
| anthropic-sonnet-4-6 | claude-sonnet-4-6 | 5 | 5 | 0 | 0 | none |
| groq-gpt-oss-120b | openai/gpt-oss-120b | 2 | 2 | 0 | 0 | none |
| groq-gpt-oss-20b | openai/gpt-oss-20b | 2 | 1 | 1 | 0 | json_generation_invalid (1) |

## Failed runs

| backend | week | stage | class | error |
|---|---|---|---|---|
| groq-gpt-oss-20b | 20260301 | brief | json_generation_invalid | groq.BadRequestError: Error code: 400 - {'error': {'message': "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.", ' |
| anthropic-opus-4-8 | 20260222 | scenarios | scenario_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for ScenarioSet: scenarios |
| anthropic-opus-4-8 | 20260329 | scenarios | scenario_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for ScenarioSet: scenarios |
