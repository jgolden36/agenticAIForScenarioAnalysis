# Backend failures in batch `alt_20261102`

14 runs failed at the weekly brief or at scenario generation, before any domain model ran.

| backend | model | runs | ok | failed at brief | failed at scenarios | principal error |
|---|---|---|---|---|---|---|
| groq-qwen3.8-27b | qwen/qwen3.8-27b | 8 | 8 | 0 | 0 | none |
| anthropic-haiku-4-5 | claude-haiku-4-5-20251001 | 8 | 1 | 7 | 0 | brief_schema_validation (7) |
| groq-qwen3.6-27b | qwen/qwen3.6-27b | 8 | 1 | 0 | 7 | scenario_count_short (6); scenario_schema_validation (1) |

## Failed runs

| backend | week | stage | class | error |
|---|---|---|---|---|
| groq-qwen3.6-27b | 20260215 | scenarios | scenario_count_short | ValueError: Scenario generation returned 4 of 5 scenarios; the reply may have been truncated at the output-token cap (PIPELINE_LLM_MAX_COMPLETION_TOKENS). |
| groq-qwen3.6-27b | 20260222 | scenarios | scenario_count_short | ValueError: Scenario generation returned 4 of 5 scenarios; the reply may have been truncated at the output-token cap (PIPELINE_LLM_MAX_COMPLETION_TOKENS). |
| groq-qwen3.6-27b | 20260301 | scenarios | scenario_count_short | ValueError: Scenario generation returned 4 of 5 scenarios; the reply may have been truncated at the output-token cap (PIPELINE_LLM_MAX_COMPLETION_TOKENS). |
| groq-qwen3.6-27b | 20260308 | scenarios | scenario_count_short | ValueError: Scenario generation returned 4 of 5 scenarios; the reply may have been truncated at the output-token cap (PIPELINE_LLM_MAX_COMPLETION_TOKENS). |
| groq-qwen3.6-27b | 20260315 | scenarios | scenario_count_short | ValueError: Scenario generation returned 4 of 5 scenarios; the reply may have been truncated at the output-token cap (PIPELINE_LLM_MAX_COMPLETION_TOKENS). |
| groq-qwen3.6-27b | 20260329 | scenarios | scenario_count_short | ValueError: Scenario generation returned 4 of 5 scenarios; the reply may have been truncated at the output-token cap (PIPELINE_LLM_MAX_COMPLETION_TOKENS). |
| groq-qwen3.6-27b | 20260405 | scenarios | scenario_schema_validation | langchain_core.exceptions.OutputParserException: Failed to parse ScenarioSet from completion [{"crisis_description": "In February 2026, the Strait of Hormuz — t |
| anthropic-haiku-4-5 | 20260222 | brief | brief_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for WeeklyBrief: observed_indicators |
| anthropic-haiku-4-5 | 20260301 | brief | brief_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for WeeklyBrief: observed_indicators |
| anthropic-haiku-4-5 | 20260308 | brief | brief_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for WeeklyBrief: observed_indicators |
| anthropic-haiku-4-5 | 20260315 | brief | brief_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for WeeklyBrief: observed_indicators |
| anthropic-haiku-4-5 | 20260322 | brief | brief_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for WeeklyBrief: observed_indicators |
| anthropic-haiku-4-5 | 20260329 | brief | brief_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for WeeklyBrief: observed_indicators |
| anthropic-haiku-4-5 | 20260405 | brief | brief_schema_validation | pydantic_core._pydantic_core.ValidationError: 1 validation error for WeeklyBrief: observed_indicators |
