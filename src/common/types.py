"""Core enums and type definitions used across the pipeline."""

from enum import Enum


class Scenario(str, Enum):
    """The four scenarios from the 2x2 scenario matrix.

    Axes: Duration (swift vs prolonged) x Escalation (contained vs escalated).
    """

    A = "swift_contained"
    B = "prolonged_contained"
    C = "swift_escalated"
    D = "prolonged_escalated"


class AnalyticalLevel(str, Enum):
    """Ordered analytical levels that determine execution sequencing.

    Information flows downward: combat -> commodity -> short-run macro -> long-run macro.
    """

    COMBAT = "combat"
    COMMODITY = "commodity"
    SHORT_RUN_MACRO = "short_run_macro"
    LONG_RUN_MACRO_STRATEGIC = "long_run_macro_strategic"


# Execution order for analytical levels
ANALYTICAL_LEVEL_ORDER = [
    AnalyticalLevel.COMBAT,
    AnalyticalLevel.COMMODITY,
    AnalyticalLevel.SHORT_RUN_MACRO,
    AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC,
]


class CommoditySystem(str, Enum):
    """Domain model groupings by commodity system."""

    WATER = "water"
    OIL = "oil"
    LNG = "lng"
    HELIUM_SEMICONDUCTORS = "helium_semiconductors"
    FERTILIZER_AGRICULTURE = "fertilizer_agriculture"
    SHIPPING = "shipping"
    MACROECONOMIC = "macroeconomic"
    ENERGY_SYSTEMS = "energy_systems"


class TimeHorizon(str, Enum):
    """Time horizon for outcome classification."""

    SHORT_RUN = "short_run"
    LONG_RUN = "long_run"


class OutcomeScope(str, Enum):
    """Scope dimension for outcome classification."""

    MICRO = "micro"
    MACRO = "macro"
    STRATEGIC = "strategic"


class ConfidenceLevel(str, Enum):
    """Confidence annotation for extracted parameters."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ValidationStatus(str, Enum):
    """Status of analyst validation at checkpoints."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class ModelExecutionStatus(str, Enum):
    """Status of a domain model execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
