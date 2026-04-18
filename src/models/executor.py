"""Model execution manager with GPU-aware scheduling.

Handles dispatching model runs across the analytical level hierarchy,
parallelizing within levels and sequencing across levels. Provides:

- Bounded concurrency via asyncio.Semaphore (honours max_parallel_models)
- GPU device assignment with round-robin rotation
- ProcessPoolExecutor for CPU-bound Python-native models (GIL avoidance)
- ThreadPoolExecutor for I/O-bound models (subprocess, API calls)
- Per-model environment injection (CUDA_VISIBLE_DEVICES, OMP_NUM_THREADS)
- Retry logic for transient failures
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from src.common.logging import get_logger
from src.common.types import ANALYTICAL_LEVEL_ORDER, ModelExecutionStatus, Scenario
from src.models.base import ModelAdapter, ModelOutput, ResourceRequirements
from src.models.registry import ModelRegistry
from src.pipeline.config import ExecutionConfig
from src.pipeline.state import ModelExecutionResult

logger = get_logger(__name__)


def _detect_gpu_devices() -> list[int]:
    """Detect available CUDA devices from the environment."""
    visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not visible:
        try:
            import torch
            return list(range(torch.cuda.device_count()))
        except (ImportError, RuntimeError):
            return []
    return [int(d.strip()) for d in visible.split(",") if d.strip().isdigit()]


def _run_model_in_process(
    adapter_class: type,
    adapter_init_kwargs: dict,
    native_inputs: Any,
    env_overrides: dict[str, str],
) -> ModelOutput:
    """Top-level function for ProcessPoolExecutor (must be picklable).

    Reconstructs the adapter in the child process and executes it.
    """
    original_env = {}
    for k, v in env_overrides.items():
        original_env[k] = os.environ.get(k)
        os.environ[k] = v
    try:
        adapter = adapter_class(**adapter_init_kwargs)
        return adapter.execute(native_inputs)
    finally:
        for k, orig in original_env.items():
            if orig is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = orig


class GPUAllocator:
    """Round-robin GPU device allocator for concurrent model execution."""

    def __init__(self, devices: list[int], reserved: int = 0) -> None:
        usable = devices[reserved:] if reserved < len(devices) else devices
        self._devices = usable if usable else [0]
        self._index = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> int:
        """Get the next available GPU device index."""
        async with self._lock:
            device = self._devices[self._index % len(self._devices)]
            self._index += 1
            return device

    @property
    def device_count(self) -> int:
        return len(self._devices)


class ModelExecutor:
    """Manages parallel/sequential execution of domain models.

    Respects analytical-level ordering:
    combat -> commodity -> short-run macro -> long-run macro/strategic.
    Parallelizes within each level with bounded concurrency.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ExecutionConfig | None = None,
    ) -> None:
        self.registry = registry
        self.config = config or ExecutionConfig()
        self._semaphore = asyncio.Semaphore(self.config.max_parallel_models)

        gpu_devices = (
            self.config.gpu.available_devices
            or _detect_gpu_devices()
        )
        self._gpu_allocator = GPUAllocator(
            gpu_devices,
            reserved=self.config.gpu.reserve_for_llm,
        )

        if self.config.worker_type == "process":
            self._pool = ProcessPoolExecutor(
                max_workers=self.config.max_parallel_models
            )
        else:
            self._pool = ThreadPoolExecutor(
                max_workers=self.config.max_parallel_models
            )

    def shutdown(self) -> None:
        """Release executor resources."""
        self._pool.shutdown(wait=False)

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
            adapters_with_params = [
                a for a in adapters if a.model_id in parameter_sets
            ]

            if not adapters_with_params:
                continue

            logger.info(
                f"Executing {len(adapters_with_params)} models at "
                f"{level.value} level for scenario {scenario_id.value}"
            )

            tasks = [
                self._execute_with_semaphore(
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

    async def _execute_with_semaphore(
        self,
        adapter: ModelAdapter,
        scenario_id: Scenario,
        params: dict[str, Any],
    ) -> ModelExecutionResult:
        """Acquire the concurrency semaphore before executing."""
        async with self._semaphore:
            return await self._execute_with_retry(adapter, scenario_id, params)

    async def _execute_with_retry(
        self,
        adapter: ModelAdapter,
        scenario_id: Scenario,
        params: dict[str, Any],
    ) -> ModelExecutionResult:
        """Execute with optional retries for transient failures."""
        max_attempts = (
            self.config.max_retries + 1 if self.config.retry_failed_models else 1
        )
        last_result: ModelExecutionResult | None = None

        for attempt in range(max_attempts):
            result = await self._execute_single(adapter, scenario_id, params)

            if result.status != ModelExecutionStatus.FAILED:
                return result

            last_result = result
            if attempt < max_attempts - 1:
                wait = 2 ** attempt
                logger.warning(
                    f"Model {adapter.model_id} failed (attempt {attempt + 1}/{max_attempts}), "
                    f"retrying in {wait}s: {result.error_message}"
                )
                await asyncio.sleep(wait)

        return last_result  # type: ignore[return-value]

    def _build_env_overrides(
        self, reqs: ResourceRequirements, gpu_device: int | None,
    ) -> dict[str, str]:
        """Build environment variable overrides for a model execution."""
        env = {}

        if gpu_device is not None:
            env["CUDA_VISIBLE_DEVICES"] = str(gpu_device)

        threads = self.config.cpu_threads_per_model
        if reqs.supports_multi_threading:
            threads = max(threads, reqs.max_threads)

        env["OMP_NUM_THREADS"] = str(threads)
        env["MKL_NUM_THREADS"] = str(threads)
        env["OPENBLAS_NUM_THREADS"] = str(threads)
        env["JULIA_NUM_THREADS"] = str(threads)

        return env

    async def _execute_single(
        self,
        adapter: ModelAdapter,
        scenario_id: Scenario,
        params: dict[str, Any],
    ) -> ModelExecutionResult:
        """Execute a single model with GPU allocation and environment setup."""
        reqs = adapter.resource_requirements
        result = ModelExecutionResult(
            scenario_id=scenario_id,
            model_id=adapter.model_id,
            status=ModelExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        gpu_device: int | None = None
        if reqs.requires_gpu:
            gpu_device = await self._gpu_allocator.acquire()
            logger.info(f"Model {adapter.model_id} assigned GPU device {gpu_device}")

        env_overrides = self._build_env_overrides(reqs, gpu_device)

        try:
            validation = adapter.validate_inputs(params)
            if not validation.valid:
                result.status = ModelExecutionStatus.FAILED
                result.error_message = (
                    f"Input validation failed: {'; '.join(validation.errors)}"
                )
                result.completed_at = datetime.now(timezone.utc)
                return result

            native_inputs = adapter.translate_inputs(params)

            loop = asyncio.get_event_loop()

            if reqs.prefers_process_isolation and isinstance(self._pool, ProcessPoolExecutor):
                output: ModelOutput = await asyncio.wait_for(
                    loop.run_in_executor(
                        self._pool,
                        _run_model_in_process,
                        type(adapter),
                        adapter.__dict__,
                        native_inputs,
                        env_overrides,
                    ),
                    timeout=self.config.default_timeout_seconds,
                )
            else:
                # Thread-pool path: set env vars in-thread, execute, restore
                original_env: dict[str, str | None] = {}
                for k, v in env_overrides.items():
                    original_env[k] = os.environ.get(k)
                    os.environ[k] = v
                try:
                    output = await asyncio.wait_for(
                        loop.run_in_executor(self._pool, adapter.execute, native_inputs),
                        timeout=self.config.default_timeout_seconds,
                    )
                finally:
                    for k, orig in original_env.items():
                        if orig is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = orig

            output.gpu_device = gpu_device
            output.worker_id = f"pid-{os.getpid()}"

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
