# Backend failures in batch `20260701_020011`

37 runs failed at the weekly brief or at scenario generation, before any domain model ran.

| backend | model | runs | ok | failed at brief | failed at scenarios | principal error |
|---|---|---|---|---|---|---|
| anthropic-sonnet-4-6 | claude-sonnet-4-6 | 8 | 8 | 0 | 0 | none |
| groq-llama4-scout | meta-llama/llama-4-scout-17b-16e-instruct | 8 | 7 | 1 | 0 | brief_schema_validation (1) |
| groq-gpt-oss-120b | openai/gpt-oss-120b | 8 | 6 | 2 | 0 | json_generation_invalid (2) |
| groq-gpt-oss-20b | openai/gpt-oss-20b | 8 | 6 | 2 | 0 | brief_schema_validation (1); json_generation_invalid (1) |
| anthropic-opus-4-8 | claude-opus-4-8 | 8 | 0 | 8 | 0 | temperature_deprecated (8) |
| groq-llama-3.1-8b | llama-3.1-8b-instant | 8 | 0 | 8 | 0 | json_schema_unsupported (8) |
| groq-llama-3.3-70b | llama-3.3-70b-versatile | 8 | 0 | 8 | 0 | json_schema_unsupported (8) |
| groq-qwen3-32b | qwen/qwen3-32b | 8 | 0 | 8 | 0 | json_schema_unsupported (8) |

## Failed runs

| backend | week | stage | class | error |
|---|---|---|---|---|
| anthropic-opus-4-8 | 20260215 | brief | temperature_deprecated | anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': '`temperature` is deprecated for this model |
| groq-llama-3.3-70b | 20260215 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama-3.1-8b | 20260215 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-qwen3-32b | 20260215 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| anthropic-opus-4-8 | 20260222 | brief | temperature_deprecated | anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': '`temperature` is deprecated for this model |
| groq-llama-3.3-70b | 20260222 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama-3.1-8b | 20260222 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-qwen3-32b | 20260222 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| anthropic-opus-4-8 | 20260301 | brief | temperature_deprecated | anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': '`temperature` is deprecated for this model |
| groq-llama-3.3-70b | 20260301 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama-3.1-8b | 20260301 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-gpt-oss-20b | 20260301 | brief | json_generation_invalid | groq.BadRequestError: Error code: 400 - {'error': {'message': "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.", ' |
| groq-qwen3-32b | 20260301 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| anthropic-opus-4-8 | 20260308 | brief | temperature_deprecated | anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': '`temperature` is deprecated for this model |
| groq-llama-3.3-70b | 20260308 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama-3.1-8b | 20260308 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-gpt-oss-20b | 20260308 | brief | brief_schema_validation | langchain_core.exceptions.OutputParserException: Failed to parse WeeklyBrief from completion {"week_start": "2026-03-08", "week_end": "2026-03-15", "headline":  |
| groq-qwen3-32b | 20260308 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| anthropic-opus-4-8 | 20260315 | brief | temperature_deprecated | anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': '`temperature` is deprecated for this model |
| groq-llama-3.3-70b | 20260315 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama-3.1-8b | 20260315 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-qwen3-32b | 20260315 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| anthropic-opus-4-8 | 20260322 | brief | temperature_deprecated | anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': '`temperature` is deprecated for this model |
| groq-llama-3.3-70b | 20260322 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama-3.1-8b | 20260322 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-qwen3-32b | 20260322 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama4-scout | 20260322 | brief | brief_schema_validation | langchain_core.exceptions.OutputParserException: Failed to parse WeeklyBrief from completion {"week_start": "2026-03-22", "week_end": "2026-03-29", "headline":  |
| anthropic-opus-4-8 | 20260329 | brief | temperature_deprecated | anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': '`temperature` is deprecated for this model |
| groq-llama-3.3-70b | 20260329 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama-3.1-8b | 20260329 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-gpt-oss-120b | 20260329 | brief | json_generation_invalid | groq.BadRequestError: Error code: 400 - {'error': {'message': "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.", ' |
| groq-qwen3-32b | 20260329 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| anthropic-opus-4-8 | 20260405 | brief | temperature_deprecated | anthropic.BadRequestError: Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', 'message': '`temperature` is deprecated for this model |
| groq-llama-3.3-70b | 20260405 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-llama-3.1-8b | 20260405 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
| groq-gpt-oss-120b | 20260405 | brief | json_generation_invalid | groq.BadRequestError: Error code: 400 - {'error': {'message': "Failed to validate JSON. Please adjust your prompt. See 'failed_generation' for more details.", ' |
| groq-qwen3-32b | 20260405 | brief | json_schema_unsupported | groq.BadRequestError: Error code: 400 - {'error': {'message': 'This model does not support response format `json_schema`. See supported models at https://consol |
