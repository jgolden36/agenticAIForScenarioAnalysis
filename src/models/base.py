"""Abstract base class for domain model adapters.

Every domain model in the inventory is wrapped by a ModelAdapter subclass
that handles input translation, execution, and output parsing. The adapter
pattern accommodates models in Python, Julia, GAMS, R, AnyLogic, and Excel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem


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
