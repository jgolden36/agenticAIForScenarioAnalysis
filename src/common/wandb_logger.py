"""Optional Weights & Biases integration for the Hormuz pipeline.

Each pipeline stage (scenarios, parameter extraction, model execution,
synthesis) opens its own W&B run, all tied together via the ``group``
parameter (set to ``HORMUZ_RUN_ID``). This pattern was chosen over a
single shared run for two reasons:

1.  The pipeline runs in two execution modes — a single-node sequential
    driver (``slurm/jobs/empire_ai_alpha.job``) and a multi-process
    SLURM array chain (``slurm/submit_pipeline.sh``). A single shared
    W&B run would require coordinated writes from many concurrent
    processes, which W&B's resume mechanics handle awkwardly. Run
    groups, by contrast, are the documented W&B pattern for
    distributed multi-process workflows and aggregate cleanly in the UI
    regardless of execution order.

2.  The synthesis stage acts as the natural aggregator: it reads the
    same per-task state files as it does for the report and uploads
    them as a single W&B Artifact, plus four consolidated tables
    (scenarios / parameters / model results / synthesis outcomes).
    Live, per-task visibility is preserved through the per-stage
    summary metrics.

Activation rules (in order of precedence):
    * ``WANDB_DISABLED=true``           → fully disabled (pure no-op).
    * ``HORMUZ_WANDB_DISABLED=true``    → pipeline-side disable switch.
    * ``wandb`` package not installed   → no-op (logged once).
    * Otherwise enabled.

When enabled but ``WANDB_API_KEY`` is unset, callers should set
``WANDB_MODE=offline`` (recommended on Empire AI compute nodes that
lack outbound HTTPS) so wandb writes locally and can be ``wandb sync``
'd from a login node afterwards. The logger does not enforce a mode;
it inherits whatever wandb's own env-var resolution decides.

All public methods are safe to call when the logger is disabled. They
return ``None`` and do not raise.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

logger = logging.getLogger(__name__)

# Cache the import attempt so we don't spam warnings on every stage.
_WANDB_IMPORT_ATTEMPTED = False
_WANDB_AVAILABLE = False
_wandb: Any = None


def _try_import_wandb() -> bool:
    """Import wandb lazily and remember the outcome."""
    global _WANDB_IMPORT_ATTEMPTED, _WANDB_AVAILABLE, _wandb
    if _WANDB_IMPORT_ATTEMPTED:
        return _WANDB_AVAILABLE
    _WANDB_IMPORT_ATTEMPTED = True
    try:
        import wandb as _w  # type: ignore[import-not-found]

        _wandb = _w
        _WANDB_AVAILABLE = True
        return True
    except ImportError:
        logger.info(
            "wandb is not installed; pipeline will run without "
            "Weights & Biases logging. Install with `pip install -e .[wandb]` "
            "to enable."
        )
        _WANDB_AVAILABLE = False
        return False


def _is_disabled_via_env() -> bool:
    """Check the env switches that fully disable the integration."""
    for var in ("WANDB_DISABLED", "HORMUZ_WANDB_DISABLED"):
        if os.environ.get(var, "").lower() in ("1", "true", "yes"):
            return True
    return False


def per_task_logging_enabled() -> bool:
    """Whether to open a W&B run for each parameter/model array task.

    Per-task runs give live status in the UI but produce O(scenarios x
    models) runs per pipeline run. Default is ON; opt out with
    ``HORMUZ_WANDB_LOG_PER_TASK=0`` to keep the project clean (only
    scenarios + synthesis runs are then created).
    """
    val = os.environ.get("HORMUZ_WANDB_LOG_PER_TASK", "1").lower()
    return val in ("1", "true", "yes")


# ---------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------


class WandbLogger:
    """Thin wrapper around a wandb.Run with safe no-op behavior.

    Construct via :meth:`for_stage` (the supported entry point); the
    bare constructor is internal.
    """

    def __init__(self, run: Any | None, stage: str, group: str) -> None:
        self._run = run
        self.stage = stage
        self.group = group

    @property
    def enabled(self) -> bool:
        """True iff a real W&B run is attached."""
        return self._run is not None

    @property
    def run(self) -> Any | None:
        """The underlying wandb.Run (or None when disabled)."""
        return self._run

    @property
    def url(self) -> str | None:
        """Public URL of this run, or None when disabled / offline."""
        if self._run is None:
            return None
        return getattr(self._run, "url", None)

    # --------------------------- core logging ---------------------------

    def log_metrics(
        self,
        metrics: dict[str, Any],
        *,
        step: int | None = None,
        commit: bool = True,
    ) -> None:
        """Log scalar metrics. Step is optional and free-form."""
        if self._run is None:
            return
        try:
            kwargs: dict[str, Any] = {"data": metrics, "commit": commit}
            if step is not None:
                kwargs["step"] = step
            self._run.log(**kwargs)
        except Exception as exc:  # never let logging crash the pipeline
            logger.warning(f"wandb log_metrics failed: {exc}")

    def log_summary(self, summary: dict[str, Any]) -> None:
        """Set summary fields (visible at the top of the run page)."""
        if self._run is None:
            return
        try:
            for k, v in summary.items():
                self._run.summary[k] = v
        except Exception as exc:
            logger.warning(f"wandb log_summary failed: {exc}")

    def log_table(
        self,
        name: str,
        columns: Sequence[str],
        rows: Iterable[Sequence[Any]],
    ) -> None:
        """Log a table under ``name``."""
        if self._run is None or _wandb is None:
            return
        try:
            tbl = _wandb.Table(columns=list(columns), data=[list(r) for r in rows])
            self._run.log({name: tbl}, commit=True)
        except Exception as exc:
            logger.warning(f"wandb log_table('{name}') failed: {exc}")

    def log_artifact(
        self,
        name: str,
        artifact_type: str,
        files: Iterable[Path | str],
        *,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Upload a list of files as a single named W&B Artifact.

        Files that do not exist are silently skipped (with a warning),
        which matches the pipeline's "graceful degradation" philosophy:
        a missing report shouldn't break the run record.
        """
        if self._run is None or _wandb is None:
            return
        try:
            art = _wandb.Artifact(
                name=name,
                type=artifact_type,
                description=description,
                metadata=metadata or {},
            )
            n_added = 0
            for f in files:
                p = Path(f)
                if not p.exists():
                    logger.warning(f"wandb artifact: skipping missing file {p}")
                    continue
                if p.is_dir():
                    art.add_dir(str(p))
                else:
                    art.add_file(str(p))
                n_added += 1
            if n_added == 0:
                logger.warning(
                    f"wandb artifact '{name}': no files added; not logging."
                )
                return
            self._run.log_artifact(art)
        except Exception as exc:
            logger.warning(f"wandb log_artifact('{name}') failed: {exc}")

    def alert(self, title: str, text: str, level: str = "INFO") -> None:
        """Emit a W&B alert (if the wandb plan supports it)."""
        if self._run is None or _wandb is None:
            return
        try:
            wandb_level = getattr(_wandb.AlertLevel, level.upper(), None)
            if wandb_level is None:
                wandb_level = _wandb.AlertLevel.INFO
            self._run.alert(title=title, text=text, level=wandb_level)
        except Exception as exc:
            logger.debug(f"wandb alert failed (often disabled on free plan): {exc}")

    def finish(self, exit_code: int = 0) -> None:
        """Close the W&B run."""
        if self._run is None:
            return
        try:
            self._run.finish(exit_code=exit_code)
        except Exception as exc:
            logger.warning(f"wandb finish failed: {exc}")
        finally:
            self._run = None

    # --------------------------- helpers ---------------------------

    @classmethod
    def for_stage(
        cls,
        stage: str,
        *,
        run_name: str | None = None,
        config: dict[str, Any] | None = None,
        tags: Iterable[str] | None = None,
        notes: str | None = None,
    ) -> "WandbLogger":
        """Create (or no-op) a W&B run for one pipeline stage.

        Resolves project / entity / group from environment variables so
        the same call site works for the SLURM driver, the array
        chain, and ad-hoc local runs.

        Parameters
        ----------
        stage:
            Short tag for the stage ("scenarios", "parameters",
            "models", "synthesis"). Used as ``job_type`` in W&B and as
            the default run name suffix.
        run_name:
            Explicit ``name`` for the run. If omitted, defaults to
            ``"<group>/<stage>"`` (or ``"<group>/<stage>/<task_id>"``
            for array tasks).
        config:
            Run config dict (hyperparams, model versions, ...).
        tags / notes:
            Forwarded to ``wandb.init`` unchanged.
        """
        group = os.environ.get(
            "HORMUZ_RUN_ID",
            os.environ.get("WANDB_RUN_GROUP", "hormuz-local"),
        )

        if _is_disabled_via_env():
            logger.info("wandb disabled via env var; skipping init")
            return cls(run=None, stage=stage, group=group)

        if not _try_import_wandb():
            return cls(run=None, stage=stage, group=group)

        # Default run name: encode the group + stage (+ task index in
        # array mode) so runs are immediately identifiable in the UI.
        if run_name is None:
            task_id = os.environ.get("SLURM_ARRAY_TASK_ID")
            if task_id is not None and task_id != "" and task_id != "single":
                run_name = f"{group}/{stage}/{int(task_id):03d}"
            else:
                run_name = f"{group}/{stage}"

        # Aggregate cluster context into the run config. Cheap to log
        # and invaluable for after-action review.
        slurm_ctx = {
            k: os.environ.get(k)
            for k in (
                "SLURM_JOB_ID",
                "SLURM_JOB_NAME",
                "SLURM_ARRAY_JOB_ID",
                "SLURM_ARRAY_TASK_ID",
                "SLURMD_NODENAME",
                "SLURM_GPUS_ON_NODE",
                "SLURM_CPUS_PER_TASK",
                "SLURM_MEM_PER_NODE",
                "SLURM_JOB_PARTITION",
            )
            if os.environ.get(k) is not None
        }
        full_config = {
            "stage": stage,
            "hormuz_run_id": group,
            "slurm": slurm_ctx,
            "pipeline_llm_provider": os.environ.get("PIPELINE_LLM_PROVIDER"),
            "pipeline_llm_model": os.environ.get("PIPELINE_LLM_MODEL"),
        }
        if config:
            full_config.update(config)

        try:
            run = _wandb.init(
                project=os.environ.get("WANDB_PROJECT", "hormuz-pipeline"),
                entity=os.environ.get("WANDB_ENTITY") or None,
                group=group,
                job_type=stage,
                name=run_name,
                tags=list(tags) if tags else ["hormuz", stage],
                notes=notes,
                config=full_config,
                # New run per process; resume is not needed because runs
                # are scoped per stage / per task and aggregated by group.
                reinit=True,
                # Do not have wandb intercept tqdm / hijack stdout.
                settings=_wandb.Settings(
                    silent=True,
                    console="off",
                    disable_meta=True,
                ),
            )
            logger.info(
                f"wandb run started: stage={stage} group={group} "
                f"name={run_name} url={getattr(run, 'url', '<offline>')}"
            )
            return cls(run=run, stage=stage, group=group)
        except Exception as exc:
            logger.warning(
                f"wandb.init failed for stage='{stage}' (continuing without "
                f"wandb logging): {exc}"
            )
            return cls(run=None, stage=stage, group=group)


# ---------------------------------------------------------------------
# Domain-specific convenience helpers
#
# These do *not* re-implement the wandb client; they only provide
# consistent table / metric shapes so downstream UI dashboards work
# the same regardless of which stage emitted the data.
# ---------------------------------------------------------------------


@contextmanager
def stage_run(stage: str, **init_kwargs: Any) -> Iterator[WandbLogger]:
    """Context manager around :meth:`WandbLogger.for_stage`.

    Ensures ``finish`` is always called and propagates the exit code
    of the surrounding block (0 on clean exit, non-zero on exception)
    to the W&B run state so the run is marked appropriately.
    """
    wb = WandbLogger.for_stage(stage, **init_kwargs)
    exit_code = 0
    try:
        yield wb
    except Exception:
        exit_code = 1
        raise
    finally:
        wb.finish(exit_code=exit_code)


def log_scenario_narratives(
    wb: WandbLogger, narratives: list[dict[str, Any]]
) -> None:
    """Log the four scenario narratives as a table + summary metrics."""
    if not wb.enabled:
        return

    rows = []
    for n in narratives:
        assumptions = n.get("quantitative_assumptions", {}) or {}
        rows.append(
            [
                n.get("scenario_id"),
                n.get("label"),
                n.get("validation_status"),
                len(assumptions),
                _short(n.get("narrative", ""), 240),
                ", ".join(f"{k}={v}" for k, v in list(assumptions.items())[:6])
                + (" ..." if len(assumptions) > 6 else ""),
            ]
        )
    wb.log_table(
        "scenarios/narratives",
        ["scenario_id", "label", "validation_status",
         "n_assumptions", "narrative_excerpt", "assumptions_excerpt"],
        rows,
    )
    wb.log_summary({"scenarios/count": len(narratives)})


def log_parameter_extraction(
    wb: WandbLogger,
    *,
    scenario_id: str,
    model_id: str,
    parameters: list[dict[str, Any]],
    runtime_seconds: float | None = None,
) -> None:
    """Log one parameter-extraction task."""
    if not wb.enabled:
        return

    by_conf: dict[str, int] = {}
    for p in parameters:
        c = p.get("confidence") or "unknown"
        by_conf[c] = by_conf.get(c, 0) + 1

    metrics: dict[str, Any] = {
        "params/n_extracted": len(parameters),
        "params/by_confidence/high": by_conf.get("high", 0),
        "params/by_confidence/medium": by_conf.get("medium", 0),
        "params/by_confidence/low": by_conf.get("low", 0),
    }
    if runtime_seconds is not None:
        metrics["params/runtime_seconds"] = runtime_seconds
    wb.log_metrics(metrics)

    rows = [
        [
            scenario_id,
            model_id,
            p.get("name"),
            p.get("value"),
            p.get("unit"),
            p.get("confidence"),
            _short(p.get("extraction_note") or "", 200),
        ]
        for p in parameters
    ]
    wb.log_table(
        "parameters/values",
        ["scenario_id", "model_id", "name", "value", "unit",
         "confidence", "extraction_note"],
        rows,
    )
    wb.log_summary(
        {
            "scenario_id": scenario_id,
            "model_id": model_id,
            "n_parameters": len(parameters),
        }
    )


def log_model_execution(wb: WandbLogger, result: dict[str, Any]) -> None:
    """Log one model-execution result (status, runtime, output sample)."""
    if not wb.enabled:
        return

    status = result.get("status", "unknown")
    runtime = result.get("runtime_seconds")
    metrics: dict[str, Any] = {
        "models/status_index": _STATUS_TO_INDEX.get(status, -1),
    }
    if runtime is not None:
        metrics["models/runtime_seconds"] = runtime
    wb.log_metrics(metrics)

    outputs = result.get("outputs") or {}
    output_excerpt = ", ".join(
        f"{k}={v}" for k, v in list(outputs.items())[:6]
    )
    if len(outputs) > 6:
        output_excerpt += " ..."

    wb.log_table(
        "models/runs",
        [
            "scenario_id",
            "model_id",
            "status",
            "runtime_seconds",
            "node",
            "slurm_job_id",
            "task_id",
            "n_outputs",
            "output_excerpt",
            "error_message",
        ],
        [
            [
                result.get("scenario_id"),
                result.get("model_id"),
                status,
                runtime,
                result.get("node"),
                result.get("slurm_job_id"),
                result.get("task_id"),
                len(outputs),
                output_excerpt,
                _short(result.get("error_message") or "", 240),
            ]
        ],
    )
    wb.log_summary(
        {
            "scenario_id": result.get("scenario_id"),
            "model_id": result.get("model_id"),
            "status": status,
            "runtime_seconds": runtime,
        }
    )


def log_synthesis_summary(
    wb: WandbLogger,
    *,
    synthesis_state: dict[str, Any],
    model_results: list[dict[str, Any]],
    parameter_results: list[dict[str, Any]],
) -> None:
    """Log the synthesis stage's aggregate tables and high-level metrics.

    This is the canonical "rollup" view for a pipeline run: regardless
    of whether per-task runs were enabled, the synthesis run will
    contain every model result, every extracted parameter, every
    consistency flag, and every synthesised outcome.
    """
    if not wb.enabled:
        return

    # Headline metrics
    wb.log_metrics(
        {
            "synthesis/model_results_count": synthesis_state.get(
                "model_results_count", len(model_results)
            ),
            "synthesis/completed": synthesis_state.get("completed", 0),
            "synthesis/skipped": synthesis_state.get("skipped", 0),
            "synthesis/failed": synthesis_state.get("failed", 0),
            "synthesis/bash_failures": synthesis_state.get(
                "bash_failures_count", 0
            ),
            "synthesis/consistency_flags": len(
                synthesis_state.get("consistency_flags", [])
            ),
            "synthesis/outcomes": len(
                synthesis_state.get("synthesis_results", [])
            ),
        }
    )

    # Aggregate model-results table
    wb.log_table(
        "synthesis/all_model_results",
        [
            "scenario_id",
            "model_id",
            "status",
            "runtime_seconds",
            "node",
            "error_message",
        ],
        [
            [
                r.get("scenario_id"),
                r.get("model_id"),
                r.get("status"),
                r.get("runtime_seconds"),
                r.get("node"),
                _short(r.get("error_message") or "", 240),
            ]
            for r in model_results
        ],
    )

    # Aggregate parameters
    param_rows: list[list[Any]] = []
    for ps in parameter_results:
        for p in ps.get("parameters", []):
            param_rows.append(
                [
                    ps.get("scenario_id"),
                    ps.get("model_id"),
                    p.get("name"),
                    p.get("value"),
                    p.get("unit"),
                    p.get("confidence"),
                ]
            )
    wb.log_table(
        "synthesis/all_parameters",
        ["scenario_id", "model_id", "name", "value", "unit", "confidence"],
        param_rows,
    )

    # Consistency flags
    wb.log_table(
        "synthesis/consistency_flags",
        ["scenario_id", "category", "severity", "description",
         "models_involved"],
        [
            [
                f.get("scenario_id"),
                f.get("category"),
                f.get("severity"),
                _short(f.get("description") or "", 240),
                ", ".join(f.get("models_involved") or []),
            ]
            for f in synthesis_state.get("consistency_flags", [])
        ],
    )

    # Synthesis outcomes
    wb.log_table(
        "synthesis/outcomes",
        [
            "scenario_id",
            "time_horizon",
            "outcome_scope",
            "outcome_variable",
            "value",
            "source_model_id",
            "narrative_summary",
        ],
        [
            [
                o.get("scenario_id"),
                o.get("time_horizon"),
                o.get("outcome_scope"),
                o.get("outcome_variable"),
                o.get("value"),
                o.get("source_model_id"),
                _short(o.get("narrative_summary") or "", 240),
            ]
            for o in synthesis_state.get("synthesis_results", [])
        ],
    )


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------

# A small numeric encoding so model status shows up nicely in W&B
# scalar plots (W&B's Lines panels need numeric values; the human-
# readable string is preserved in the table column).
_STATUS_TO_INDEX = {
    "completed": 1,
    "skipped": 0,
    "running": -1,
    "pending": -2,
    "failed": -3,
}


def _short(text: str, limit: int) -> str:
    """Truncate text to ``limit`` chars with an ellipsis suffix."""
    if not text:
        return ""
    text = str(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."
