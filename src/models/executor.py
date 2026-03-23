"""Model execution manager.

Handles dispatching model runs across the analytical level hierarchy,
parallelizing within levels and sequencing across levels. Captures
execution metadata and handles failures gracefully.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from src.common.logging import get_logger
from src.common.types import ANALYTICAL_LEVEL_ORDER, ModelExecutionStatus, Scenario
from src.models.base import ModelAdapter, ModelOutput
from src.models.registry import ModelRegistry
from src.pipeline.config import ExecutionConfig
from src.pipeline.state import ModelExecutionResult

logger = get_logger(__name__)


class ModelExecutor:
    """Manages parallel/sequential execution of domain models.

    Respects analytical-level ordering:
    combat -> commodity -> short-run macro -> long-run macro/strategic.
    Parallelizes within each level.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ExecutionConfig | None = None,
    ) -> None:
        self.registry = registry
        self.config = config or ExecutionConfig()

    async def execute_all(
        self,
        scenario_id: Scenario,
        parameter_sets: dict[str, dict[str, Any]],
    ) -> list[ModelExecutionResult]:
        """Execute all models for a scenario, respecting level ordering.

        Args:
            scenario_id: Which scenario to execute for.
            parameter_sets: Dict of model_id -> parameter dict.

        Returns:
            List of execution results for all model runs.
        """
        all_results: list[ModelExecutionResult] = []

        for level in ANALYTICAL_LEVEL_ORDER:
            adapters = self.registry.get_by_analytical_level(level)
            # Filter to adapters that have parameters
            adapters_with_params = [
                a for a in adapters if a.model_id in parameter_sets
            ]

            if not adapters_with_params:
                continue

            logger.info(
                f"Executing {len(adapters_with_params)} models at "
                f"{level.value} level for scenario {scenario_id.value}"
            )

            # Run models at this level in parallel
            tasks = [
                self._execute_single(
                    adapter, scenario_id, parameter_sets[adapter.model_id]
                )
                for adapter in adapters_with_params
            ]

            level_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in level_results:
                if isinstance(result, Exception):
                    logger.error(f"Unexpected error in model execution: {result}")
                else:
                    all_results.append(result)

        return all_results

    async def _execute_single(
        self,
        adapter: ModelAdapter,
        scenario_id: Scenario,
        params: dict[str, Any],
    ) -> ModelExecutionResult:
        """Execute a single model, capturing all metadata.

        Individual model failures are isolated — they produce a FAILED
        result but do not crash the pipeline.
        """
        result = ModelExecutionResult(
            scenario_id=scenario_id,
            model_id=adapter.model_id,
            status=ModelExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        try:
            # Validate inputs
            validation = adapter.validate_inputs(params)
            if not validation.valid:
                result.status = ModelExecutionStatus.FAILED
                result.error_message = (
                    f"Input validation failed: {'; '.join(validation.errors)}"
                )
                result.completed_at = datetime.now(timezone.utc)
                return result

            # Translate inputs
            native_inputs = adapter.translate_inputs(params)

            # Execute model (run in executor to not block event loop)
            loop = asyncio.get_event_loop()
            output: ModelOutput = await asyncio.wait_for(
                loop.run_in_executor(None, adapter.execute, native_inputs),
                timeout=self.config.default_timeout_seconds,
            )

            result.status = ModelExecutionStatus.COMPLETED
            result.outputs = output.outputs
            result.completed_at = datetime.now(timezone.utc)
            if result.started_at:
                result.runtime_seconds = (
                    result.completed_at - result.started_at
                ).total_seconds()

        except NotImplementedError as e:
            result.status = ModelExecutionStatus.SKIPPED
            result.error_message = f"Model not yet implemented: {e}"
            result.completed_at = datetime.now(timezone.utc)
            logger.warning(f"Model {adapter.model_id} skipped: not implemented")

        except asyncio.TimeoutError:
            result.status = ModelExecutionStatus.FAILED
            result.error_message = (
                f"Execution timed out after {self.config.default_timeout_seconds}s"
            )
            result.completed_at = datetime.now(timezone.utc)
            logger.error(f"Model {adapter.model_id} timed out")

        except Exception as e:
            result.status = ModelExecutionStatus.FAILED
            result.error_message = f"{type(e).__name__}: {e}"
            result.completed_at = datetime.now(timezone.utc)
            logger.error(f"Model {adapter.model_id} failed: {e}")

        return result
