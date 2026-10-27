"""Abstract base class for domain model adapters.

Every domain model in the inventory is wrapped by a ModelAdapter subclass
that handles input translation, execution, and output parsing. The adapter
pattern accommodates models in Python, Julia, GAMS, R, AnyLogic, and Excel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem, ImplementationMode


class ValidationResult(BaseModel):
    """Result of input validation."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ResourceRequirements(BaseModel):
    """Declarative resource requirements for a model adapter.

    The executor uses these hints to schedule models across available
    CPU cores and GPU devices on the cluster.
    """

    requires_gpu: bool = Field(
        default=False,
        description="Whether this model requires GPU acceleration",
    )
    gpu_memory_gb: float = Field(
        default=0.0,
        description="Minimum GPU memory required in GB (0 = no GPU needed)",
    )
    num_gpus: int = Field(
        default=0,
        description="Number of GPU devices required",
    )
    cpu_cores: int = Field(
        default=1,
        description="Number of CPU cores preferred",
    )
    memory_gb: float = Field(
        default=4.0,
        description="RAM required in GB",
    )
    supports_multi_threading: bool = Field(
        default=False,
        description="Whether the model can exploit multiple threads internally",
    )
    max_threads: int = Field(
        default=1,
        description="Max useful threads if supports_multi_threading is True",
    )
    prefers_process_isolation: bool = Field(
        default=False,
        description=(
            "Run in a separate process instead of a thread. "
            "Set True for CPU-bound Python-native models to avoid GIL contention."
        ),
    )


class ModelOutput(BaseModel):
    """Standardized model output container.

    Adapters that have a native uncertainty mechanism (Monte Carlo
    sampling, posterior draws, ensemble members) should populate
    ``uncertainty`` directly. Adapters that do not have such a
    mechanism leave it ``None`` — the executor will then optionally
    wrap their ``execute()`` with a perturbation-based replication
    loop (see ``src.models.uncertainty``) and fill it in after the
    fact.
    """

    model_id: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    convergence_status: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    worker_id: str | None = Field(
        default=None, description="Identifier of the worker/node that executed this model"
    )
    gpu_device: int | None = Field(
        default=None, description="CUDA device index used (if GPU model)"
    )
    uncertainty: "UncertaintyReport | None" = Field(
        default=None,
        description=(
            "Per-output quantiles, std, and provenance. Populated either "
            "by the adapter (native UQ) or by the executor's perturbation "
            "wrapper. None means no UQ was performed."
        ),
    )


class UncertaintyEstimate(BaseModel):
    """Per-output uncertainty estimate for a single scalar output key."""

    mean: float
    std: float
    quantiles: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Quantile name -> value. Keys are stringified percentiles "
            "such as 'p05', 'p25', 'p50', 'p75', 'p95'."
        ),
    )
    n_samples: int = Field(
        default=0,
        description="Number of replications used to compute this estimate.",
    )

    @property
    def ci90_low(self) -> float | None:
        return self.quantiles.get("p05")

    @property
    def ci90_high(self) -> float | None:
        return self.quantiles.get("p95")


class UncertaintyReport(BaseModel):
    """Bundle of per-output uncertainty estimates plus method metadata."""

    method: str = Field(
        description=(
            "UncertaintyMethod value: 'none', 'native', 'perturbation', "
            "or 'bootstrap'."
        ),
    )
    n_replicates: int = 0
    perturbation_pct: float | None = Field(
        default=None,
        description=(
            "For method='perturbation', the +/- multiplicative noise "
            "(percent) applied to numeric inputs."
        ),
    )
    estimates: dict[str, UncertaintyEstimate] = Field(
        default_factory=dict,
        description="Per-output-key uncertainty estimate.",
    )
    notes: str = ""
    failures: int = Field(
        default=0,
        description="Number of replicate runs that raised an exception.",
    )


class ImplementationInfo(BaseModel):
    """Static description of how an adapter implements its domain model.

    Populated per adapter so the registry can emit a run-independent
    model inventory (platform, calibration sources, key equations,
    limitations) and so the runtimes can label each execution record
    with the :class:`ImplementationMode` that was actually used.
    """

    mode_when_executed: ImplementationMode = Field(
        default=ImplementationMode.UNKNOWN,
        description=(
            "Mode ``execute()`` runs in when it returns normally and the "
            "ModelOutput carries no explicit mode marker. Config-aware "
            "adapters that branch at runtime should instead tag "
            "``ModelOutput.metadata['mode']``."
        ),
    )
    modes_available: list[ImplementationMode] = Field(
        default_factory=list,
        description="Every mode this adapter can run in (full, reduction, ...).",
    )
    display_name: str = Field(default="", description="Human-readable model name.")
    display_name_reduced: str = Field(
        default="",
        description=(
            "Name to print when the analytical reduction ran, e.g. "
            "'POLES-calibrated reduction'. Empty when no reduction exists."
        ),
    )
    platform: str = Field(default="", description="Language / runtime of the upstream model.")
    upstream_reference: str = Field(
        default="", description="Citation or URL for the upstream model."
    )
    calibration_sources: list[str] = Field(
        default_factory=list,
        description="Literature estimates the reduction is calibrated against.",
    )
    key_equations: list[str] = Field(
        default_factory=list,
        description="One-line statements of the reduced-form equations.",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Main limitations relative to the upstream model.",
    )
    license_notes: str = Field(
        default="", description="Licensing restrictions on the upstream model."
    )


# Tokens that adapters already write into ``ModelOutput.metadata`` (keys
# ``mode`` / ``execution_mode`` / ``engine``) or into ``outputs``
# (``_execution_mode``), mapped onto the canonical enum. Unknown tokens
# resolve to ``None`` so the caller can fall back to the adapter's
# declared default instead of guessing.
_MODE_TOKENS: dict[str, ImplementationMode] = {
    "analytical_mvp": ImplementationMode.ANALYTICAL_REDUCTION,
    "analytical": ImplementationMode.ANALYTICAL_REDUCTION,
    "analytical_reduction": ImplementationMode.ANALYTICAL_REDUCTION,
    "closed_form": ImplementationMode.ANALYTICAL_REDUCTION,
    "kernel_fallback": ImplementationMode.ANALYTICAL_REDUCTION,
    "mvp": ImplementationMode.ANALYTICAL_REDUCTION,
    "output_ingestion": ImplementationMode.PUBLISHED_OUTPUT_INGESTION,
    "aeo_ingestion": ImplementationMode.PUBLISHED_OUTPUT_INGESTION,
    "published_output_ingestion": ImplementationMode.PUBLISHED_OUTPUT_INGESTION,
    "ingestion": ImplementationMode.PUBLISHED_OUTPUT_INGESTION,
    "stub": ImplementationMode.STUB,
    "full_upstream": ImplementationMode.FULL_UPSTREAM,
    "subprocess": ImplementationMode.FULL_UPSTREAM,
    "remote": ImplementationMode.FULL_UPSTREAM,
    "eviews_subprocess": ImplementationMode.FULL_UPSTREAM,
    "cge_modeling": ImplementationMode.FULL_UPSTREAM,
    "octave": ImplementationMode.FULL_UPSTREAM,
    "octave_dynare": ImplementationMode.FULL_UPSTREAM,
    "dynare": ImplementationMode.FULL_UPSTREAM,
    "gams": ImplementationMode.FULL_UPSTREAM,
    "julia": ImplementationMode.FULL_UPSTREAM,
    "juliacall": ImplementationMode.FULL_UPSTREAM,
    "excel": ImplementationMode.FULL_UPSTREAM,
    "xlwings": ImplementationMode.FULL_UPSTREAM,
    "openpyxl": ImplementationMode.FULL_UPSTREAM,
    "anylogic": ImplementationMode.FULL_UPSTREAM,
    "jar": ImplementationMode.FULL_UPSTREAM,
    "r": ImplementationMode.FULL_UPSTREAM,
    "rscript": ImplementationMode.FULL_UPSTREAM,
    "rpy2": ImplementationMode.FULL_UPSTREAM,
    "native": ImplementationMode.FULL_UPSTREAM,
    "python": ImplementationMode.FULL_UPSTREAM,
    "cli": ImplementationMode.FULL_UPSTREAM,
    "api": ImplementationMode.FULL_UPSTREAM,
    "http": ImplementationMode.FULL_UPSTREAM,
    "ogcore": ImplementationMode.FULL_UPSTREAM,
    "ixmp": ImplementationMode.FULL_UPSTREAM,
    "pyomo": ImplementationMode.FULL_UPSTREAM,
    "com": ImplementationMode.FULL_UPSTREAM,
}

_MODE_METADATA_KEYS = ("mode", "execution_mode", "implementation_mode", "engine")
_MODE_OUTPUT_KEYS = ("_implementation_mode", "_execution_mode")


def normalize_mode_token(token: Any) -> ImplementationMode | None:
    """Map a free-form mode token to :class:`ImplementationMode` (or None)."""
    if token is None:
        return None
    if isinstance(token, ImplementationMode):
        return token
    key = str(token).strip().lower().replace("-", "_").replace(" ", "_")
    return _MODE_TOKENS.get(key)


def resolve_implementation_mode(
    output: "ModelOutput | None",
    adapter: "ModelAdapter | None" = None,
    outputs: dict[str, Any] | None = None,
) -> ImplementationMode:
    """Determine the implementation mode a completed execution used.

    Precedence: explicit markers in ``ModelOutput.metadata`` (``mode``,
    ``execution_mode``, ``implementation_mode``, ``engine``), then
    markers in the outputs dict (``_execution_mode``,
    ``_used_analytical_mvp``, ``_macro_source`` ending in
    ``kernel_fallback``), then the adapter's declared
    ``implementation_info.mode_when_executed``, then ``UNKNOWN``.
    ``outputs`` may be passed on its own (e.g. when re-reading persisted
    ``output.json`` files) in which case ``output`` can be ``None``.
    """
    metadata: dict[str, Any] = {}
    if output is not None:
        metadata = output.metadata or {}
        if outputs is None:
            outputs = output.outputs
    outputs = outputs or {}

    for key in _MODE_METADATA_KEYS:
        mode = normalize_mode_token(metadata.get(key))
        if mode is not None:
            return mode
    for key in _MODE_OUTPUT_KEYS:
        mode = normalize_mode_token(outputs.get(key))
        if mode is not None:
            return mode
    if outputs.get("_used_analytical_mvp") is True:
        return ImplementationMode.ANALYTICAL_REDUCTION
    macro_source = outputs.get("_macro_source")
    if isinstance(macro_source, str) and macro_source.endswith("kernel_fallback"):
        return ImplementationMode.ANALYTICAL_REDUCTION
    if adapter is not None:
        declared = adapter.implementation_info.mode_when_executed
        if declared != ImplementationMode.UNKNOWN:
            return declared
    return ImplementationMode.UNKNOWN


class ModelAdapter(ABC):
    """Abstract base class for all domain model adapters.

    Subclass this for each domain model in the inventory. Concrete adapters
    must implement all abstract methods. The `execute` method should raise
    NotImplementedError for stub implementations until the real model is
    integrated.

    Resource requirements are declared via the `resource_requirements` property
    so the executor can schedule models across GPUs and CPU cores on the cluster.
    """

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Unique identifier for this model."""

    @property
    @abstractmethod
    def commodity_system(self) -> CommoditySystem:
        """Which commodity system this model belongs to."""

    @property
    @abstractmethod
    def analytical_level(self) -> AnalyticalLevel:
        """Which analytical level this model operates at."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of the model."""

    @property
    def resource_requirements(self) -> ResourceRequirements:
        """Declare compute resource requirements for scheduling.

        Override in subclasses that need GPU, extra CPU cores, or process
        isolation. Defaults to a minimal single-threaded CPU profile.
        """
        return ResourceRequirements()

    @property
    def implementation_info(self) -> ImplementationInfo:
        """Static implementation description used by the model inventory.

        Override in subclasses. The default is deliberately conservative
        (``UNKNOWN`` mode, no calibration sources) so an adapter that has
        not been annotated is reported as such rather than mislabelled.
        """
        return ImplementationInfo()

    @abstractmethod
    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        """Validate that the provided parameters meet the model's requirements.

        Args:
            params: Dictionary of parameter name -> value.

        Returns:
            ValidationResult with any errors or warnings.
        """

    @abstractmethod
    def translate_inputs(self, params: dict[str, Any]) -> Any:
        """Translate standardized parameters into the model's native input format.

        Args:
            params: Validated parameter dictionary.

        Returns:
            Model-native input format (file path, data structure, etc.).
        """

    @abstractmethod
    def execute(self, inputs: Any) -> ModelOutput:
        """Execute the model with translated inputs.

        Args:
            inputs: Model-native inputs from translate_inputs.

        Returns:
            ModelOutput containing results and metadata.

        Raises:
            NotImplementedError: For stub adapters awaiting real model integration.
        """

    @abstractmethod
    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse raw model output into standardized ModelOutput format.

        Args:
            raw: Raw output from the model execution.

        Returns:
            Standardized ModelOutput.
        """


# Resolve forward reference on ModelOutput.uncertainty.
ModelOutput.model_rebuild()
