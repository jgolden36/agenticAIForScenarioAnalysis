"""Request and response contract between the game engine and the adjudicator.

The game serialises its crisis state into a :class:`RoundRequest` once per round. The
adjudicator answers with a :class:`RoundResponse` whose every number names the model run it
came from. Both are plain Pydantic v2 models so the same shapes serve the HTTP API and direct
in-process calls.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class WorldState(BaseModel):
    """The crisis variables the game tracks (design report, Hormuz subgame spec)."""

    transit_capacity_pct: float = Field(100.0, ge=0.0, le=100.0,
                                        description="Strait throughput as pct of the pre-crisis 20.9 mb/d")
    mine_density: float = Field(0.0, ge=0.0, description="Relative mine density, 0 = clear")
    escalation_rung: int = Field(0, ge=0, le=7, description="Kahn-style ladder rung 0 (calm) to 7 (regional war)")
    qatar_damaged_share: float = Field(0.0, ge=0.0, le=1.0,
                                       description="Share of Qatar LNG export capacity knocked out")
    bypass_used_mbd: float = Field(0.0, ge=0.0, description="Bypass pipeline volume in use this round")
    stock_release_mbd: float = Field(0.0, ge=0.0, description="Stocks reaching the market this round")
    demand_restraint_mbd: float = Field(0.0, ge=0.0, description="Emergency demand restraint in force")
    war_risk_premium_pct: float = Field(0.25, ge=0.0, description="War-risk premium, pct of hull per transit")
    weeks_elapsed: int = Field(0, ge=0, description="Rounds since the closure began")
    expected_remaining_weeks: int = Field(8, ge=0, description="Control cell's published duration expectation")
    rerouting_via_cape: bool = Field(True, description="Whether displaced cargoes take the Cape route")
    helium_reserve_release_mmscf: float = Field(0.0, ge=0.0, description="Strategic helium release, MMscf")


class TeamSpec(BaseModel):
    region: str = Field("ROW", description="Unified macro-kernel region id")


class RoundRequest(BaseModel):
    game_id: str
    turn: int = Field(1, ge=0)
    seed: int = 0
    world: WorldState = Field(default_factory=WorldState)
    teams: dict[str, TeamSpec] = Field(default_factory=dict,
                                       description="seat id -> region; empty means use the baseline teams")


class ModelProvenance(BaseModel):
    model_id: str
    output_key: str
    value: Any
    implementation_mode: str
    runtime_ms: float


class ModelRun(BaseModel):
    model_id: str
    status: str
    label: str | None = Field(None, description="Which call this was when one model runs several times a round")
    implementation_mode: str = "unknown"
    runtime_ms: float = 0.0
    inputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class Fallback(BaseModel):
    model_id: str
    reason: str


class LaneState(BaseModel):
    rerouting_cost_multiplier: float = 1.0
    effective_fleet_capacity_loss_pct: float = 0.0
    war_risk_insurance_premium_pct: float = 0.0


class MacroRow(BaseModel):
    region: str
    gdp_impact_pct: float
    cpi_inflation_pct: float
    consumption_impact_pct: float


class RoundResponse(BaseModel):
    status: str = "ok"
    game_id: str
    turn: int
    scenario_label: str
    as_of: str
    multipliers: dict[str, float] = Field(default_factory=dict,
                                          description="price ratio to baseline per commodity, this round")
    peak_multipliers: dict[str, float] = Field(default_factory=dict,
                                               description="the model's full-disruption peak, before the ramp")
    lane: LaneState = Field(default_factory=LaneState)
    shocks: dict[str, float] = Field(default_factory=dict)
    macro_by_team: dict[str, MacroRow] = Field(default_factory=dict)
    provenance: list[ModelProvenance] = Field(default_factory=list)
    runs: list[ModelRun] = Field(default_factory=list)
    overrides: list[dict[str, Any]] = Field(default_factory=list)
    flags: list[dict[str, Any]] = Field(default_factory=list)
    fallbacks: list[Fallback] = Field(default_factory=list)
    derived: dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: float = 0.0
    no_llm: bool = True
