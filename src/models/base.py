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


class ModelOutput(BaseModel):
    """Standardized model output container."""

    model_id: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    convergence_status: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class ModelAdapter(ABC):
    """Abstract base class for all domain model adapters.

    Subclass this for each domain model in the inventory. Concrete adapters
    must implement all abstract methods. The `execute` method should raise
    NotImplementedError for stub implementations until the real model is
    integrated.
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
