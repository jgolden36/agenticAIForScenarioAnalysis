"""Core enums and type definitions used across the pipeline."""

from enum import Enum


class Scenario(str, Enum):
    """Scenario identifiers used throughout the pipeline.

    The first four (A-D) are the canonical 2x2 quadrants from the
    Schwartz scenario matrix. Axes: Duration (swift vs prolonged) x
    Escalation (contained vs escalated).

    ``E`` is a prescribed tail-risk scenario added outside the 2x2
    matrix. It assumes a prolonged-and-escalated path (like D) but
    additionally stipulates that major Persian Gulf infrastructure --
    desalination plants, Qatari LNG export terminals, and Saudi /
    UAE oil loading terminals -- is destroyed or severely damaged
    during the conflict, producing a multi-year reconstruction and
    investment overhang and a substantially deeper supply shock than
    D. Configured via ``additional_scenarios`` in the scenario
    framework (see ``configs/scenario_frameworks/hormuz_2026.yaml``).
    """

    A = "swift_contained"
    B = "prolonged_contained"
    C = "swift_escalated"
    D = "prolonged_escalated"
    E = "infrastructure_collapse"


class AnalyticalLevel(str, Enum):
    """Ordered analytical levels that determine execution sequencing.

    Information flows downward: combat -> commodity -> commodity_downstream
    -> short-run macro -> long-run macro. The COMMODITY_DOWNSTREAM tier
    hosts commodity-system models whose inputs are themselves derived
    from other commodity-tier model outputs (e.g. SimRLFab and the
    Argonne Helium ABM consume world_helium_model outputs).
    """

    COMBAT = "combat"
    COMMODITY = "commodity"
    COMMODITY_DOWNSTREAM = "commodity_downstream"
    SHORT_RUN_MACRO = "short_run_macro"
    LONG_RUN_MACRO_STRATEGIC = "long_run_macro_strategic"


# Execution order for analytical levels
ANALYTICAL_LEVEL_ORDER = [
    AnalyticalLevel.COMBAT,
    AnalyticalLevel.COMMODITY,
    AnalyticalLevel.COMMODITY_DOWNSTREAM,
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


class UncertaintyMethod(str, Enum):
    """How an adapter's output uncertainty was quantified.

    ``NATIVE`` — the adapter ran its own internal uncertainty mechanism
    (Monte Carlo, posterior draws, ensemble members) and returned a
    distribution natively.
    ``PERTURBATION`` — the executor wrapped the adapter and re-ran it N
    times with multiplicative Gaussian noise on numeric inputs.
    ``BOOTSTRAP`` — the executor wrapped the adapter and re-ran it N
    times with resampled / jittered numeric inputs to estimate sampling
    error.
    ``NONE`` — no uncertainty quantification was performed.
    """

    NONE = "none"
    NATIVE = "native"
    PERTURBATION = "perturbation"
    BOOTSTRAP = "bootstrap"
