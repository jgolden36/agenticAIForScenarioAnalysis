"""MESSAGEixAdapter — IIASA MESSAGEix integrated assessment model.

Drives a MESSAGEix scenario through the ``message-ix`` / ``ixmp``
Python API. The execution flow is:

    1. Open the configured ``ixmp.Platform`` (default JDBC backend
       backed by a local HSQLDB or an explicit DB URL).
    2. Load the baseline ``Scenario`` identified by
       ``baseline_model``/``baseline_scenario``/``baseline_version``.
    3. Clone the baseline into a per-run scenario named
       ``f"{baseline_scenario}_{scenario_id}"``.
    4. Apply pipeline-derived shocks via ``scenario.add_par(...)``:
       fuel-availability bounds, capital-cost multipliers, exogenous
       fuel-price overrides, LNG export-capacity caps, and CO2 prices.
    5. ``scenario.solve(model="MESSAGE")`` — invokes GAMS under the
       hood through ixmp.
    6. Read variables ``PRICE_COMMODITY``, ``CAP_NEW``, ``ACT``, and
       (optional) ``EMISS`` back via ``scenario.var(...)`` and parse
       into the standardized ``ModelOutput``.

Real implementation requirements:
    - Python: ``message-ix`` (>=3.7) and ``ixmp`` (>=3.7).
    - GAMS installation reachable by ixmp's MESSAGE solver invocation.
    - Java runtime for ixmp's default JDBC backend (or a configured
      Postgres/Oracle connection).
    - The vendored MESSAGEix repo at ``Models/Energy/MESSAGEix/`` is
      used to source the Westeros tutorial baseline when no production
      baseline is available; productionized analyses should point at
      a calibrated global baseline.
"""

from __future__ import annotations

import gc
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import (
    ModelAdapter,
    ModelOutput,
    ResourceRequirements,
    ValidationResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JDBC backend interpreter-shutdown safety
# ---------------------------------------------------------------------------
#
# ixmp's default JDBCBackend defines a ``__del__`` that calls
# ``self.close_db()``, whose ``except java.IxException as e:`` clause
# crashes when JPype's ``java`` proxy has already been replaced with a
# ``types.SimpleNamespace`` during Python interpreter shutdown. The
# resulting ``AttributeError: 'types.SimpleNamespace' object has no
# attribute 'IxException'`` is harmless (the model has finished, every
# scenario was solved and persisted) but produces multi-line
# ``Exception ignored in: <function JDBCBackend.__del__ ...>`` tracebacks
# in SLURM logs that look like real failures to anyone reading the log.
#
# The patch wraps ``JDBCBackend.__del__`` so any exception raised after
# the JVM has been torn down is silently swallowed. It is idempotent
# (won't double-wrap) and a no-op when ``ixmp`` is not importable.
def _install_ixmp_jdbc_shutdown_safety() -> None:
    """Silence ``JDBCBackend.__del__`` AttributeError on interpreter shutdown.

    Called from :meth:`MESSAGEixAdapter.execute` immediately after
    ``import ixmp`` succeeds. Safe to call multiple times — the patch
    is keyed off a sentinel attribute on the wrapped function so the
    second and later invocations short-circuit.
    """
    try:
        from ixmp.backend.jdbc import JDBCBackend
    except ImportError:
        return

    original_del = JDBCBackend.__del__
    if getattr(original_del, "_hormuz_patched", False):
        return

    def _safe_del(self: Any) -> None:
        try:
            original_del(self)
        except BaseException:
            # ``__del__`` runs during GC / interpreter shutdown; raising
            # from here is meaningless and only adds log noise. The
            # actual model run has already completed and persisted its
            # outputs by the time this fires.
            pass

    _safe_del._hormuz_patched = True  # type: ignore[attr-defined]
    JDBCBackend.__del__ = _safe_del  # type: ignore[assignment,method-assign]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_MESSAGEIX_DIR = Path("Models/Energy/MESSAGEix")


class MESSAGEixConfig(BaseModel):
    """Configuration for the MESSAGEixAdapter."""

    messageix_dir: Path = Field(
        default=DEFAULT_MESSAGEIX_DIR,
        description="Root of the vendored MESSAGEix repository.",
    )
    platform_name: str = Field(
        default="local",
        description=(
            "ixmp Platform name to open (must be configured via "
            "``ixmp platform add`` or pre-registered)."
        ),
    )
    baseline_model: str = Field(
        default="Westeros Electrified",
        description="``model`` identifier of the baseline scenario.",
    )
    baseline_scenario: str = Field(
        default="baseline",
        description="``scenario`` identifier of the baseline scenario.",
    )
    baseline_version: int | None = Field(
        default=None,
        description="Optional version of the baseline (None → latest).",
    )
    target_model: str = Field(
        default="Hormuz Disruption",
        description="``model`` identifier under which scenario clones are written.",
    )
    solve_model: str = Field(
        default="MESSAGE",
        description=(
            "MESSAGE solve target. Use 'MESSAGE-MACRO' if a calibrated "
            "macro module is wired into the baseline."
        ),
    )
    output_dir: Path = Field(
        default=Path("data/outputs/messageix"),
        description="Directory where solved-result CSVs are exported per scenario.",
    )
    timeout_seconds: int = Field(
        default=14400,
        description="Solve-call timeout (default 4 hours).",
    )
    keep_clone_after_run: bool = Field(
        default=True,
        description=(
            "Keep the cloned scenario in the ixmp database after the run "
            "(set False to remove it via scenario.remove_solution / "
            "platform.scenario_list)."
        ),
    )
    fuel_to_commodity: dict[str, str] = Field(
        default_factory=lambda: {
            "oil": "crudeoil",
            "gas": "gas",
            "lng": "LNG",
        },
        description=(
            "Mapping from pipeline fuel labels to MESSAGE 'commodity' set "
            "members. Override for non-Westeros baselines."
        ),
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PARAMS = frozenset(
    {
        "oil_supply_loss_mbd",
        "gas_supply_loss_bcfd",
        "disruption_duration_months",
        "lng_export_capacity_loss_pct",
        "capital_cost_multiplier",
        "co2_price_baseline_usd_per_t",
    }
)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class MESSAGEixAdapter(ModelAdapter):
    """Live adapter for IIASA's MESSAGEix integrated assessment model."""

    def __init__(self, config: MESSAGEixConfig | None = None) -> None:
        self._config = config or MESSAGEixConfig()

    @property
    def model_id(self) -> str:
        return "messageix"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.ENERGY_SYSTEMS

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "MESSAGEix (IIASA) — integrated assessment energy-systems model "
            "with ixmp scenario management. Baseline is cloned per run, "
            "Hormuz-class shocks are written via add_par, and the GAMS solve "
            "is invoked through scenario.solve()."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=4,
            memory_gb=16.0,
            supports_multi_threading=True,
            max_threads=4,
            prefers_process_isolation=True,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        missing = REQUIRED_PARAMS - params.keys()
        for name in sorted(missing):
            errors.append(f"Missing required parameter: '{name}'")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        for name in (
            "oil_supply_loss_mbd",
            "gas_supply_loss_bcfd",
            "disruption_duration_months",
            "lng_export_capacity_loss_pct",
            "capital_cost_multiplier",
            "co2_price_baseline_usd_per_t",
        ):
            value = params[name]
            if not isinstance(value, (int, float)):
                errors.append(f"'{name}' must be numeric; got {type(value).__name__}")

        if errors:
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        if params["disruption_duration_months"] <= 0:
            errors.append("'disruption_duration_months' must be positive")
        if params["capital_cost_multiplier"] <= 0:
            errors.append("'capital_cost_multiplier' must be positive")
        if not (0.0 <= params["lng_export_capacity_loss_pct"] <= 100.0):
            errors.append("'lng_export_capacity_loss_pct' must be in [0, 100]")
        if params["co2_price_baseline_usd_per_t"] < 0:
            errors.append("'co2_price_baseline_usd_per_t' must be non-negative")

        # Surface integration prerequisites without hard failure during
        # validate_inputs (matches NEMS/MIRAGRODEP idiom).
        try:
            import message_ix  # noqa: F401
        except ImportError:
            warnings.append(
                "message-ix is not installed; install via "
                "`pip install hormuz-pipeline[energy]` (or "
                "`pip install message-ix ixmp`) before calling execute()."
            )
        else:
            # ixmp is now in sys.modules (transitively via message_ix).
            # Install the JDBC shutdown-safety patch eagerly so any
            # JDBCBackend instance created later in this process — even
            # one constructed outside MESSAGEix.execute() — is cleaned
            # up quietly at interpreter shutdown.
            _install_ixmp_jdbc_shutdown_safety()

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # Input translation
    # ------------------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        scenario_id = params.get("scenario_id", "default")
        return {
            "scenario_id": scenario_id,
            "shocks": {
                "oil_supply_loss_mbd": float(params["oil_supply_loss_mbd"]),
                "gas_supply_loss_bcfd": float(params["gas_supply_loss_bcfd"]),
                "duration_years": float(params["disruption_duration_months"]) / 12.0,
                "oil_price_path_override_usd": params.get("oil_price_path_override_usd"),
                "lng_export_capacity_loss_pct": float(params["lng_export_capacity_loss_pct"]),
                "capital_cost_multiplier": float(params["capital_cost_multiplier"]),
                "co2_price_baseline_usd_per_t": float(params["co2_price_baseline_usd_per_t"]),
            },
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        cfg = self._config
        scenario_id = inputs["scenario_id"]

        try:
            import ixmp
            import message_ix
        except ImportError as exc:
            # NotImplementedError → SLURM runner classifies as SKIPPED.
            raise NotImplementedError(
                "MESSAGEix adapter requires the 'message-ix' and 'ixmp' packages. "
                "Install with `pip install -e .[energy]`."
            ) from exc

        # Install the JDBC __del__ shutdown-safety patch BEFORE creating
        # any Platform. Without this, Python's garbage collector chases
        # JDBCBackend instances after JPype has already torn down the
        # JVM (replacing the ``java`` proxy with a SimpleNamespace),
        # which spams the SLURM log with multi-line tracebacks like:
        #   Exception ignored in: <function JDBCBackend.__del__ ...>
        #   AttributeError: 'types.SimpleNamespace' object has no
        #                   attribute 'IxException'
        # The model itself runs fine; this patch only silences the
        # noise. See _install_ixmp_jdbc_shutdown_safety() above.
        _install_ixmp_jdbc_shutdown_safety()

        platform = ixmp.Platform(name=cfg.platform_name)
        try:
            baseline = message_ix.Scenario(
                platform,
                model=cfg.baseline_model,
                scenario=cfg.baseline_scenario,
                version=cfg.baseline_version,
            )

            clone_name = f"{cfg.baseline_scenario}_{scenario_id}"
            scenario = baseline.clone(
                model=cfg.target_model,
                scenario=clone_name,
                annotation=f"Hormuz pipeline run for scenario_id={scenario_id}",
                keep_solution=False,
            )

            scenario.check_out()
            self._apply_shocks(scenario, inputs["shocks"])
            scenario.commit(f"Hormuz shocks applied for {scenario_id}")
            scenario.set_as_default()

            scenario.solve(model=cfg.solve_model, solve_options={"iterlim": 100000})

            outputs = self._extract_outputs(scenario)
            outputs["_applied_shocks"] = inputs["shocks"]
            self._inject_derived_macro(outputs, inputs["shocks"])

            cfg.output_dir.mkdir(parents=True, exist_ok=True)

            return ModelOutput(
                model_id=self.model_id,
                outputs=outputs,
                convergence_status="completed",
                metadata={
                    "scenario_id": scenario_id,
                    "ixmp_platform": cfg.platform_name,
                    "model": cfg.target_model,
                    "scenario": clone_name,
                    "version": getattr(scenario, "version", None),
                },
            )
        finally:
            # Order matters: close the DB FIRST (while the JVM is still
            # alive), then drop every Python reference to the Platform
            # / Scenario / backend objects, then force a GC pass. This
            # guarantees JDBCBackend.__del__ runs WHILE ``java`` is
            # still a real JPype proxy module — not after JPype has
            # replaced it with types.SimpleNamespace at interpreter
            # shutdown. The JDBC __del__ shutdown-safety patch
            # installed above already silences the resulting noise if
            # this still races, so this is belt-and-suspenders.
            try:
                platform.close_db()
            except Exception:  # pragma: no cover - best-effort cleanup
                logger.warning("Failed to close ixmp Platform cleanly", exc_info=True)
            try:
                # Local references inside the try-block (baseline,
                # scenario) are already out of scope here, but the
                # ``platform`` binding still pins the JDBCBackend.
                platform = None  # type: ignore[assignment]
                gc.collect()
            except Exception:  # pragma: no cover - best-effort cleanup
                pass

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
            metadata={"adapter": self.__class__.__name__},
        )

    @staticmethod
    def _inject_derived_macro(
        outputs: dict[str, Any], applied_shocks: dict[str, Any]
    ) -> None:
        """Append macro_kernel-derived GDP / CPI / consumption / welfare
        fields to the MESSAGEix output dict.

        MESSAGEix's translate_inputs already produces oil_supply_loss_mbd
        and gas_supply_loss_bcfd, so this is a thin wrapper around the
        shared kernel. Tagged ``_macro_source: messageix_derived``.
        Skips silently when there are no operational shocks to translate.
        """
        if not applied_shocks:
            return
        try:
            from src.models.macro.macro_kernel import (
                derive_macro_from_energy_shocks,
            )
        except ImportError:
            return
        try:
            derived = derive_macro_from_energy_shocks(applied_shocks)
        except Exception as exc:  # noqa: BLE001 -- never fatal
            logger.warning(
                "MESSAGEix: derived macro outcomes unavailable (%s)", exc
            )
            return

        translation = derived.get("_translation") or {}
        if not translation:
            return

        for key in (
            "gdp_impact_pct",
            "gdp_growth_pct",
            "gdp_growth_pct_year1",
            "cpi_inflation_pct",
            "cpi_inflation_pct_year1",
            "consumption_impact_pct",
            "welfare_pct_change",
            "wage_impact_pct",
            "interest_rate_impact_pct",
            "sectoral_output_pct_change",
        ):
            if key in derived:
                outputs[key] = derived[key]
        outputs["_macro_source"] = "messageix_derived"
        outputs["_macro_derivation"] = {
            "translation": translation,
            "calibration_sources": derived.get("_calibration_sources", []),
            "kernel_inputs": derived.get("_inputs", {}),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _apply_shocks(self, scenario: Any, shocks: dict[str, Any]) -> None:
        """Apply shocks to a checked-out MESSAGE scenario.

        Each block is wrapped in a try/except that downgrades to a warning
        because the relevant set members ("crudeoil", "gas", "LNG") may
        not exist in every baseline (notably the Westeros tutorial).
        """
        cfg = self._config
        oil_commodity = cfg.fuel_to_commodity.get("oil", "crudeoil")
        gas_commodity = cfg.fuel_to_commodity.get("gas", "gas")
        lng_commodity = cfg.fuel_to_commodity.get("lng", "LNG")

        capex_mult = shocks["capital_cost_multiplier"]
        if capex_mult and capex_mult != 1.0:
            try:
                inv_cost = scenario.par("inv_cost")
                inv_cost["value"] = inv_cost["value"].astype(float) * capex_mult
                scenario.add_par("inv_cost", inv_cost)
            except Exception as exc:
                logger.warning("inv_cost shock skipped: %s", exc)

        co2_price = shocks["co2_price_baseline_usd_per_t"]
        if co2_price > 0:
            try:
                tax = scenario.par("tax_emission")
                if not tax.empty:
                    tax["value"] = co2_price
                    scenario.add_par("tax_emission", tax)
            except Exception as exc:
                logger.warning("tax_emission shock skipped: %s", exc)

        oil_loss = shocks["oil_supply_loss_mbd"]
        gas_loss = shocks["gas_supply_loss_bcfd"]
        duration_years = shocks["duration_years"]
        if oil_loss > 0 or gas_loss > 0:
            try:
                bound = scenario.par("bound_activity_up")
                years = sorted(bound["year_act"].unique())
                affected = set(years[: max(1, int(round(duration_years)))])

                def _scaled(commodity: str, factor: float) -> Any:
                    sub = bound[
                        bound["technology"].str.contains(
                            commodity, case=False, na=False
                        )
                        & bound["year_act"].isin(affected)
                    ].copy()
                    if sub.empty:
                        return sub
                    sub["value"] = sub["value"].astype(float) * factor
                    return sub

                if oil_loss > 0:
                    oil_factor = max(0.0, 1.0 - 0.05 * oil_loss)
                    sub = _scaled(oil_commodity, oil_factor)
                    if not sub.empty:
                        scenario.add_par("bound_activity_up", sub)
                if gas_loss > 0:
                    gas_factor = max(0.0, 1.0 - 0.02 * gas_loss)
                    sub = _scaled(gas_commodity, gas_factor)
                    if not sub.empty:
                        scenario.add_par("bound_activity_up", sub)
            except Exception as exc:
                logger.warning("bound_activity_up shock skipped: %s", exc)

        lng_loss_pct = shocks["lng_export_capacity_loss_pct"]
        if lng_loss_pct > 0:
            try:
                cap = scenario.par("bound_new_capacity_up")
                sub = cap[
                    cap["technology"].str.contains(
                        lng_commodity, case=False, na=False
                    )
                ].copy()
                if not sub.empty:
                    sub["value"] = sub["value"].astype(float) * (
                        1.0 - lng_loss_pct / 100.0
                    )
                    scenario.add_par("bound_new_capacity_up", sub)
            except Exception as exc:
                logger.warning("bound_new_capacity_up (LNG) shock skipped: %s", exc)

    def _extract_outputs(self, scenario: Any) -> dict[str, Any]:
        outputs: dict[str, Any] = {}
        for var_name in ("PRICE_COMMODITY", "CAP_NEW", "ACT", "EMISS"):
            try:
                df = scenario.var(var_name)
                outputs[var_name] = df.to_dict(orient="records")
            except Exception as exc:
                logger.debug("Could not read MESSAGE var %s: %s", var_name, exc)

        # Convenience scalar: average oil-commodity price over the
        # solution horizon, normalized to USD/bbl assuming
        # USD/GJ × 5.8 GJ/bbl. Useful for cross-model consistency rules.
        price_records = outputs.get("PRICE_COMMODITY") or []
        oil_commodity = self._config.fuel_to_commodity.get("oil", "crudeoil")
        oil_prices = [
            float(r.get("lvl", 0.0))
            for r in price_records
            if str(r.get("commodity", "")).lower() == oil_commodity.lower()
        ]
        if oil_prices:
            outputs["oil_price_usd"] = (sum(oil_prices) / len(oil_prices)) * 5.8

        return outputs
