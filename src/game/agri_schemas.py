"""Request and response contract for the agricultural adjudicator (``POST /adjudicate/agri``).

The game's ``agri`` ruleset (repo ``EconomicWarGames``) serialises its round into an
:class:`AgriRoundRequest`: the world fertilizer and gas shocks, the crop price changes of its own
Tier 0 clearing, and per team the fertilizer pass-through, subsidy and any pending drought. The
answer is an :class:`AgriRoundResponse` whose every number names the model run it came from.

Crop names on the wire are always the game's: ``wheat``, ``rice``, ``maize``, ``soybeans``. The
adjudicator maps them to each adapter's own names (APSIM's ``soybean``, the futures model's
``corn``) through ``configs/game/agri_2027_baseline.yaml``.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from .schemas import Fallback, MacroRow, ModelProvenance, ModelRun

GAME_CROPS: tuple[str, ...] = ("wheat", "rice", "maize", "soybeans")


def _check_crop_keys(value: dict[str, float], what: str) -> dict[str, float]:
    unknown = sorted(k for k in value if k not in GAME_CROPS)
    if unknown:
        raise ValueError(f"{what}: unknown crop(s) {unknown}; the game's crops are {list(GAME_CROPS)}")
    return value


class AgriWorld(BaseModel):
    """The world-level inputs of one agricultural round."""

    gas_price_change_pct: float = Field(0.0, ge=-100.0,
                                        description="Gas/LNG price change the game attributes to the Hormuz link; 0 without one")
    middle_east_fertilizer_loss_pct: float = Field(0.0, ge=0.0, le=100.0,
                                                   description="Middle East nitrogen production/export loss, 100 x Hormuz closure")
    hormuz_transit_capacity_pct: float = Field(100.0, ge=0.0, le=100.0, description="Strait throughput, pct of pre-crisis")
    fertilizer_price_change_pct: float = Field(0.0, ge=-100.0,
                                               description="The game's Tier 0 world nitrogen-fertilizer change, all components")
    hormuz_component_pct: float = Field(0.0, description="The part of fertilizer_price_change_pct the game attributes to Hormuz")
    expected_shock_months: float = Field(6.0, ge=0.0, le=120.0, description="Expected duration of the input shock")
    crop_price_change_pct: dict[str, float] = Field(default_factory=dict,
                                                    description="The game's Tier 0 world crop price change, per crop")

    @field_validator("crop_price_change_pct")
    @classmethod
    def _crops(cls, v: dict[str, float]) -> dict[str, float]:
        return _check_crop_keys(v, "crop_price_change_pct")


class AgriTeam(BaseModel):
    region: str = Field("ROW", description="Unified macro-kernel region id")
    fertilizer_passthrough: float = Field(1.0, ge=0.0, le=1.0,
                                          description="Share of the world fertilizer change that reaches this team's farm gate")
    fertilizer_subsidy_pct: float = Field(0.0, ge=0.0, le=80.0, description="Cut to the farm-gate fertilizer price level")
    water_deficit_pct_by_crop: dict[str, float] = Field(default_factory=dict,
                                                        description="Crops under a pending drought, water deficit pct (0..95)")

    @field_validator("water_deficit_pct_by_crop")
    @classmethod
    def _deficits(cls, v: dict[str, float]) -> dict[str, float]:
        _check_crop_keys(v, "water_deficit_pct_by_crop")
        bad = {k: x for k, x in v.items() if not 0.0 <= float(x) <= 95.0}
        if bad:
            raise ValueError(f"water_deficit_pct_by_crop must be within [0, 95]; got {bad}")
        return v


class AgriRoundRequest(BaseModel):
    game_id: str
    turn: int = Field(1, ge=0)
    seed: int = 0
    date: str = ""
    world: AgriWorld = Field(default_factory=AgriWorld)
    teams: dict[str, AgriTeam] = Field(default_factory=dict, description="team id (seats plus ROW) -> its inputs")


class FertilizerResult(BaseModel):
    nitrogen_price_pct: float | None = None
    phosphate_price_pct: float | None = None
    potash_price_pct: float | None = None
    fertilizer_price_index_pct: float | None = None
    world_change_pct: float = Field(0.0, description="The world nitrogen change every team's farm-gate rule used")
    source_model: str = Field("game", description="world_fertilizer, or game when the model did not run")
    implementation_mode: str = "not_run"


class YieldPair(BaseModel):
    """Percent yield change (negative = loss). ``None`` means the run for it failed."""

    n_pct: float | None = None
    water_pct: float | None = None


class AgriRoundResponse(BaseModel):
    status: str = "ok"
    game_id: str
    turn: int
    as_of: str
    baseline_id: str = ""
    fertilizer: FertilizerResult = Field(default_factory=FertilizerResult)
    farmgate_fertilizer_price_change_pct: dict[str, float] = Field(default_factory=dict)
    application_reduction_pct: dict[str, float] = Field(default_factory=dict)
    yields: dict[str, dict[str, YieldPair]] = Field(default_factory=dict)
    forward_curves: dict[str, list[float]] = Field(default_factory=dict)
    time_to_normalization_months: dict[str, int | None] = Field(default_factory=dict)
    macro_by_team: dict[str, MacroRow] = Field(default_factory=dict)
    provenance: list[ModelProvenance] = Field(default_factory=list)
    runs: list[ModelRun] = Field(default_factory=list)
    overrides: list[dict[str, Any]] = Field(default_factory=list)
    flags: list[dict[str, Any]] = Field(default_factory=list)
    fallbacks: list[Fallback] = Field(default_factory=list)
    derived: dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: float = 0.0
    no_llm: bool = True
