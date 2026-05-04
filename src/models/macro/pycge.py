"""PyCGEAdapter — Python CGE driver bound to ``cge_modeling`` (Jesse Grabowski).

The ``cge_modeling`` package (https://github.com/jessegrabowski/cge_modeling)
provides a sympy/jax-based static computable general equilibrium framework
that builds and solves CGE models from declarative algebraic specifications
plus a Social Accounting Matrix (SAM).

In this pipeline PyCGE is the lightweight, Python-native cross-validation
companion to OpenCGE (OG-Core OLG model) and MIRAGRODEP (GAMS multi-region
agricultural CGE). It accepts the same commodity price shock set as those
two adapters but solves for a static general-equilibrium response, making
it both fast and easy to instrument for sensitivity analysis.

Two execution modes:

1. **Real ``cge_modeling`` mode** — When the upstream package is installed
   AND its API matches what the adapter expects (``Model``, ``load_sam``,
   the bundled ``examples.hosoe_2region`` example, and a ``solve`` API),
   the adapter builds / loads a baseline equilibrium, applies SAM
   parameter overrides for the scenario shocks, re-solves, and reports
   percent-change-from-baseline aggregates.

2. **Analytical-MVP mode** — When ``cge_modeling`` is missing or its
   API is the pre-alpha shape that does not match the calls below
   (cge_modeling 0.0.x exposes ``CGEModel`` / ``cge_model`` /
   ``Equation`` / ``Parameter`` / ``Variable`` rather than ``Model`` /
   ``load_sam`` / ``examples.hosoe_2region``), ``execute()`` falls
   back to ``src.models.macro.macro_kernel.compute_macro_outcomes``.
   That kernel is a pure-Python, dependency-free closed-form macro
   response calibrated against Hamilton (2003, 2009 Brookings),
   Kilian (2008 RES), and Blanchard & Galí (2007), so the macro tier
   always has a runnable CGE on the cluster MVP. Mirrors the analytical
   MVP pattern used by ``poles_jrc``, ``world_helium_model``, and
   ``futures``.

Real implementation requirements:
- ``cge_modeling`` Python package (optional — analytical MVP runs without)
- A Social Accounting Matrix (SAM) — JSON or CSV. The adapter ships a
  default Hosoe-style 2-region SAM at ``data/sams/hosoe_2region.json``.
- An optional model-definition YAML (cge_modeling spec format). If absent,
  the adapter falls back to ``cge_modeling.examples.hosoe_2region``.
"""

from __future__ import annotations

import json
import logging
import pickle
import time
from pathlib import Path
from typing import Any, Literal

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
# Configuration
# ---------------------------------------------------------------------------

class PyCGEConfig(BaseModel):
    """Configuration for the PyCGE / cge_modeling driver."""

    sam_path: Path = Field(
        default=Path("data/sams/hosoe_2region.json"),
        description="Path to the Social Accounting Matrix (JSON or CSV)",
    )
    model_definition_path: Path | None = Field(
        default=None,
        description=(
            "Optional path to a cge_modeling model-definition YAML. "
            "If None, the adapter falls back to the bundled Hosoe 2-region example."
        ),
    )
    numeraire: str = Field(
        default="px[capital]",
        description="cge_modeling numeraire variable",
    )
    solver: Literal["root", "minimize", "euler"] = Field(
        default="root",
        description="cge_modeling solver: 'root' (scipy.optimize.root, default), "
                    "'minimize' (scipy.optimize.minimize), or 'euler' (homotopy).",
    )
    tol: float = Field(
        default=1e-8,
        description="Solver tolerance",
    )
    max_iter: int = Field(
        default=2000,
        description="Solver iteration cap",
    )
    baseline_cache_path: Path = Field(
        default=Path("data/pycge_baseline.pkl"),
        description="Cached baseline equilibrium (re-used across scenario runs)",
    )
    rebuild_baseline: bool = Field(
        default=False,
        description="Force rebuild of the baseline equilibrium even if cache exists",
    )
    # Mapping commodity name -> SAM parameter name(s) to perturb.
    # Each SAM parameter receives a multiplicative shock equal to
    # (1 + shock_pct/100). Use a list when one commodity touches several
    # SAM parameters.
    commodity_to_sam_param: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "oil": ["p_oil", "p_energy"],
            "lng": ["p_gas", "p_energy"],
            "fertilizer": ["p_fert", "p_intermediate"],
            "helium": ["p_helium"],
            # Water enters the macro layer only under the prescribed
            # infrastructure_collapse scenario (see the rule in
            # configs/upstream_to_macro_mapping.yaml). It maps to a
            # dedicated p_water symbol when present in the SAM and
            # also into p_intermediate as a generic intermediate-input
            # cost surrogate so SAMs without an explicit water row
            # still register the shock.
            # `_scale_parameter` silently no-ops if a SAM symbol is
            # absent, so this default is safe across SAM variants.
            "water": ["p_water", "p_intermediate"],
        },
        description=(
            "Per-commodity mapping from pipeline shock names to "
            "cge_modeling parameter symbols. Edit to match your SAM."
        ),
    )
    timeout_seconds: int = Field(
        default=600,
        description="Per-run timeout in seconds (default 10 minutes)",
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_PARAMS = frozenset(
    {
        "oil_price_shock_pct",
        "commodity_price_shocks",
        "disruption_duration_months",
    }
)


def _coerce_commodity_shocks(value: Any) -> dict[str, float] | None:
    """Best-effort flattening of common LLM-emitted shapes for ``commodity_price_shocks``.

    Mirrors :func:`src.models.macro.opencge._coerce_commodity_shocks`;
    duplicated here so the two adapters can be moved/tested in
    isolation. Accepts ``{commodity: float}``, ``{commodity: {shock,
    unit}}``, and ``{commodity: "40%"}`` and normalises to
    ``{commodity: float}``.
    """
    if not isinstance(value, dict):
        return None
    flat: dict[str, float] = {}
    for k, v in value.items():
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            flat[str(k)] = float(v)
            continue
        if isinstance(v, dict):
            inner = v.get("shock", v.get("value", v.get("pct", v.get("percent"))))
            if isinstance(inner, (int, float)) and not isinstance(inner, bool):
                flat[str(k)] = float(inner)
                continue
        if isinstance(v, str):
            try:
                flat[str(k)] = float(v.strip().rstrip("%"))
            except ValueError:
                continue
    return flat


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class PyCGEAdapter(ModelAdapter):
    """Adapter binding PyCGE to the ``cge_modeling`` Python package.

    The adapter:
    1. Loads (or builds-and-caches) a baseline equilibrium from the SAM.
    2. For each scenario, applies multiplicative shocks to the configured
       SAM parameters via ``commodity_to_sam_param``.
    3. Re-solves the model from the baseline initial values.
    4. Computes percent-change-from-baseline for headline aggregates and a
       Hicksian-equivalent welfare summary.
    """

    def __init__(self, config: PyCGEConfig | None = None) -> None:
        self._config = config or PyCGEConfig()

    @property
    def model_id(self) -> str:
        return "pycge"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.MACROECONOMIC

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.LONG_RUN_MACRO_STRATEGIC

    @property
    def description(self) -> str:
        return (
            "PyCGE (cge_modeling): static Python computable general equilibrium "
            "model. Provides a fast, pure-Python cross-validation companion to "
            "OpenCGE (OG-Core OLG) and MIRAGRODEP (GAMS multi-region). Accepts "
            "commodity price shocks and produces sectoral output, factor price, "
            "and welfare deltas from a SAM-calibrated baseline. Falls back to "
            "an analytical-MVP closed-form macro kernel when cge_modeling is "
            "unavailable, so the macro tier always has a runnable CGE."
        )

    @property
    def resource_requirements(self) -> ResourceRequirements:
        return ResourceRequirements(
            requires_gpu=False,
            cpu_cores=2,
            memory_gb=4.0,
            supports_multi_threading=True,
            max_threads=2,
            prefers_process_isolation=False,
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

        # Defensive coercion: smaller LLMs sometimes wrap each shock in
        # {shock, unit} instead of emitting a bare number. Normalise to
        # dict[str, float] in place so the rest of validation and
        # translate_inputs see the canonical shape.
        coerced = _coerce_commodity_shocks(params.get("commodity_price_shocks"))
        if coerced is not None and coerced != params.get("commodity_price_shocks"):
            params["commodity_price_shocks"] = coerced
            warnings.append(
                "'commodity_price_shocks' was normalised from an LLM-emitted "
                "nested shape to a flat dict[str, number]."
            )

        oil_shock = params["oil_price_shock_pct"]
        if not isinstance(oil_shock, (int, float)):
            errors.append(
                f"'oil_price_shock_pct' must be numeric; got {type(oil_shock).__name__}"
            )
        elif oil_shock < -100.0:
            errors.append(
                f"'oil_price_shock_pct' cannot be less than -100%; got {oil_shock}"
            )
        elif oil_shock > 500.0:
            warnings.append(
                f"'oil_price_shock_pct' is {oil_shock}%, implying more than a 5x "
                "price increase. Verify consistency with commodity-level oil model outputs."
            )

        price_shocks = params["commodity_price_shocks"]
        if not isinstance(price_shocks, dict) or len(price_shocks) == 0:
            errors.append(
                "'commodity_price_shocks' must be a non-empty dict mapping commodity "
                "names to percentage price shocks (e.g., {'lng': 40.0, 'fertilizer': 25.0})"
            )
        else:
            mapping = self._config.commodity_to_sam_param
            for commodity, shock in price_shocks.items():
                if not isinstance(shock, (int, float)):
                    errors.append(
                        f"'commodity_price_shocks[{commodity!r}]' must be numeric; "
                        f"got {type(shock).__name__}"
                    )
                    continue
                if shock < -100.0:
                    errors.append(
                        f"'commodity_price_shocks[{commodity!r}]' cannot be less than "
                        f"-100%; got {shock}"
                    )
                if commodity not in mapping:
                    warnings.append(
                        f"'commodity_price_shocks' includes '{commodity}' which is "
                        f"not in commodity_to_sam_param mapping (known: "
                        f"{sorted(mapping)}); shock will be ignored."
                    )

        duration = params["disruption_duration_months"]
        if not isinstance(duration, (int, float)):
            errors.append(
                f"'disruption_duration_months' must be numeric; got {type(duration).__name__}"
            )
        elif duration <= 0:
            errors.append(f"'disruption_duration_months' must be positive; got {duration}")
        elif duration > 24:
            warnings.append(
                f"'disruption_duration_months' is {duration}, which exceeds the "
                "expected scenario range (0–24 months). Verify this is intentional."
            )

        # Surface integration prerequisites. Missing SAM / cge_modeling /
        # model definition are warnings rather than errors because
        # execute() falls back to the analytical-MVP closed-form macro
        # kernel when the real cge_modeling path is unavailable.
        sam_path = Path(self._config.sam_path)
        if not sam_path.exists():
            warnings.append(
                f"SAM file not found at {sam_path}. The real cge_modeling "
                "path will be skipped; execute() will run the analytical-MVP "
                "macro kernel instead."
            )
        if (
            self._config.model_definition_path is not None
            and not Path(self._config.model_definition_path).exists()
        ):
            warnings.append(
                f"Model definition not found at {self._config.model_definition_path}; "
                "adapter will fall back to bundled hosoe_2region example or "
                "the analytical-MVP kernel."
            )

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # ------------------------------------------------------------------
    # Input translation
    # ------------------------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Translate pipeline shocks into a SAM-parameter override dict.

        Returns a dict with:
            scenario_id: str
            parameter_overrides: {sam_param_name: multiplicative_factor}
            duration_months: float
            applied_shocks: {commodity: shock_pct}
        """
        scenario_id = params.get("scenario_id", "default")
        mapping = self._config.commodity_to_sam_param

        all_shocks: dict[str, float] = {
            **{k: float(v) for k, v in params["commodity_price_shocks"].items()
               if isinstance(v, (int, float))},
        }
        all_shocks["oil"] = float(params["oil_price_shock_pct"])

        # Aggregate per-SAM-param multiplicative factors. When several
        # commodities map to the same SAM parameter, multiply the factors.
        overrides: dict[str, float] = {}
        applied: dict[str, float] = {}
        for commodity, shock_pct in all_shocks.items():
            sam_params = mapping.get(commodity)
            if not sam_params:
                continue
            factor = 1.0 + shock_pct / 100.0
            for sp in sam_params:
                overrides[sp] = overrides.get(sp, 1.0) * factor
            applied[commodity] = shock_pct

        return {
            "scenario_id": scenario_id,
            "parameter_overrides": overrides,
            "duration_months": float(params["disruption_duration_months"]),
            "applied_shocks": applied,
        }

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Run the real ``cge_modeling`` solver when available, else fall back
        to the analytical-MVP closed-form macro kernel.

        The fallback never raises ``ImportError`` or ``NotImplementedError``
        for missing / incompatible cge_modeling, so PyCGE always reports
        COMPLETED on the cluster MVP and the macro tier always sees a
        first-class CGE answer for every scenario. Mirrors the pattern
        used by ``poles_jrc`` and ``world_helium_model``.
        """
        if self._cge_modeling_api_available():
            try:
                return self._execute_real_cge_modeling(inputs)
            except Exception as exc:  # noqa: BLE001 -- fall through cleanly
                logger.warning(
                    "PyCGE: real cge_modeling path raised %s (%s); "
                    "falling back to analytical-MVP kernel.",
                    type(exc).__name__,
                    exc,
                )
        return self._execute_analytical_mvp(inputs)

    @staticmethod
    def _cge_modeling_api_available() -> bool:
        """Return True iff ``cge_modeling`` exposes the API this adapter
        was originally written against.

        cge_modeling at v0.0.x exposes ``CGEModel`` / ``cge_model`` /
        ``Equation`` / ``Parameter`` / ``Variable`` and does NOT expose
        ``Model`` / ``load_sam`` / ``examples.hosoe_2region``. Without
        those names the real path will fail with ImportError on the
        first call; we detect this once up-front and use the analytical
        MVP instead.
        """
        try:
            import cge_modeling  # type: ignore[import-not-found]
        except ImportError:
            return False

        # The real path needs at minimum a ``Model`` factory and either
        # ``load_sam`` or the bundled ``examples.hosoe_2region`` to
        # build a default model. If neither path is reachable, the
        # analytical MVP is the right answer.
        if not hasattr(cge_modeling, "Model"):
            return False
        if hasattr(cge_modeling, "load_sam"):
            return True
        try:
            from cge_modeling.examples import hosoe_2region  # type: ignore  # noqa: F401
            return True
        except ImportError:
            return False

    def _execute_real_cge_modeling(self, inputs: Any) -> ModelOutput:
        """Build/load baseline, apply shocks, re-solve, and standardize outputs."""
        scenario_id = inputs["scenario_id"]
        overrides = inputs["parameter_overrides"]

        start = time.time()

        # 1. Load or build baseline equilibrium.
        baseline_model, baseline_result = self._load_or_build_baseline()

        # 2. Apply shocks via cge_modeling's parameter-override interface.
        reform_model = self._clone_model(baseline_model)
        for sam_param, factor in overrides.items():
            self._scale_parameter(reform_model, sam_param, factor)

        # 3. Re-solve from baseline initial values.
        reform_result = self._solve_model(
            reform_model,
            initial_values=getattr(baseline_result, "x", None) or baseline_result,
        )

        elapsed = time.time() - start

        # 4. Standardize outputs.
        out = self._standardize_outputs(baseline_result, reform_result)
        out["_applied_shocks"] = inputs.get("applied_shocks", {})
        out["_duration_months"] = inputs.get("duration_months")
        out["_overrides"] = overrides
        out["_execution_mode"] = "cge_modeling"

        return ModelOutput(
            model_id=self.model_id,
            outputs=out,
            convergence_status="completed",
            metadata={
                "scenario_id": scenario_id,
                "elapsed_seconds": elapsed,
                "solver": self._config.solver,
                "sam_path": str(self._config.sam_path),
                "execution_mode": "cge_modeling",
            },
        )

    def _execute_analytical_mvp(self, inputs: Any) -> ModelOutput:
        """Closed-form macro response via ``macro_kernel.compute_macro_outcomes``.

        Reconstructs the ``commodity_shocks`` dict from the SAM-parameter
        overrides translation done in ``translate_inputs`` (which
        ultimately came from ``params['commodity_price_shocks']`` plus
        ``params['oil_price_shock_pct']``) and forwards to the shared
        analytical kernel. This guarantees PyCGE produces the
        synthesizer's standard macro schema -- gdp_impact_pct,
        gdp_growth_pct, cpi_inflation_pct, consumption_impact_pct,
        welfare_pct_change, sectoral_output_pct_change -- without any
        runtime dependency on cge_modeling, OG-Core, GAMS, or licensed
        binaries.
        """
        from src.models.macro.macro_kernel import compute_macro_outcomes

        scenario_id = inputs["scenario_id"]
        applied_shocks = dict(inputs.get("applied_shocks", {}))
        duration_months = float(inputs.get("duration_months", 6.0))

        start = time.time()
        kernel_out = compute_macro_outcomes(
            applied_shocks,
            duration_months,
            regime="short_run",
        )
        elapsed = time.time() - start

        out: dict[str, Any] = dict(kernel_out)
        out["_applied_shocks"] = applied_shocks
        out["_duration_months"] = duration_months
        out["_overrides"] = inputs.get("parameter_overrides", {})
        out["_used_analytical_mvp"] = True
        out["_execution_mode"] = "analytical_mvp"
        out["_provenance_note"] = (
            "PyCGE analytical-MVP closed-form macro kernel (literature-"
            "calibrated elasticities). Activates when the optional "
            "cge_modeling package is missing or its pre-alpha API does "
            "not match this adapter's expectations."
        )

        return ModelOutput(
            model_id=self.model_id,
            outputs=out,
            convergence_status="completed",
            metadata={
                "scenario_id": scenario_id,
                "elapsed_seconds": elapsed,
                "execution_mode": "analytical_mvp",
                "sam_path": str(self._config.sam_path),
            },
        )

    # ------------------------------------------------------------------
    # Helpers — built defensively to tolerate small cge_modeling API
    # variations across versions.
    # ------------------------------------------------------------------

    def _load_or_build_baseline(self) -> tuple[Any, Any]:
        """Return (model, baseline_result), using cache if available."""
        cache = Path(self._config.baseline_cache_path)
        if cache.exists() and not self._config.rebuild_baseline:
            try:
                with open(cache, "rb") as f:
                    cached = pickle.load(f)  # noqa: S301
                logger.info("PyCGE: loaded baseline from cache %s", cache)
                return cached["model"], cached["result"]
            except (OSError, pickle.UnpicklingError) as exc:
                logger.warning(
                    "PyCGE: baseline cache load failed (%s); rebuilding", exc
                )

        model = self._build_model()
        result = self._solve_model(model)

        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cache, "wb") as f:
                pickle.dump({"model": model, "result": result}, f)
        except (OSError, pickle.PicklingError) as exc:
            logger.warning("PyCGE: failed to write baseline cache: %s", exc)

        return model, result

    def _build_model(self) -> Any:
        """Construct a cge_modeling Model from configured SAM + definition.

        Tolerates two API layouts seen across cge_modeling versions:
        - newer: cge_modeling.Model.from_sam(sam_path, definition=...)
        - older: cge_modeling.load_sam(sam_path) -> SAM, then Model(SAM)
        """
        from cge_modeling import (  # type: ignore[import-not-found]
            Model,
        )

        sam = self._load_sam()

        if self._config.model_definition_path is not None and Path(
            self._config.model_definition_path
        ).exists():
            try:
                from cge_modeling import load_definition  # type: ignore
                definition = load_definition(str(self._config.model_definition_path))
                return Model(sam=sam, definition=definition,
                             numeraire=self._config.numeraire)
            except ImportError:
                pass

        # Fall back to bundled example.
        try:
            from cge_modeling.examples import hosoe_2region  # type: ignore
            return hosoe_2region.build_model(
                sam=sam, numeraire=self._config.numeraire,
            )
        except ImportError:
            pass

        # Last-resort: instantiate the Model with the SAM only and let
        # cge_modeling apply its built-in default specification.
        return Model(sam=sam, numeraire=self._config.numeraire)

    def _load_sam(self) -> Any:
        """Load the SAM from JSON or CSV.

        cge_modeling exposes ``load_sam`` for several formats; we try it first
        and fall back to a plain JSON read if the helper is unavailable.
        """
        sam_path = Path(self._config.sam_path)
        try:
            from cge_modeling import load_sam  # type: ignore
            return load_sam(str(sam_path))
        except ImportError:
            pass

        if sam_path.suffix.lower() == ".json":
            with open(sam_path) as f:
                return json.load(f)
        try:
            import pandas as pd
            return pd.read_csv(sam_path, index_col=0)
        except ImportError as exc:
            raise RuntimeError(
                f"Cannot load SAM at {sam_path}: pandas not available "
                "and cge_modeling.load_sam not exposed."
            ) from exc

    def _solve_model(self, model: Any, initial_values: Any | None = None) -> Any:
        """Invoke the cge_modeling solver with the configured method.

        Uses ``model.solve`` if available, otherwise falls back to an
        explicit equation-system solve (older cge_modeling API).
        """
        kwargs: dict[str, Any] = {
            "method": self._config.solver,
            "tol": self._config.tol,
            "max_iter": self._config.max_iter,
        }
        if initial_values is not None:
            kwargs["initial_values"] = initial_values

        if hasattr(model, "solve"):
            return model.solve(**kwargs)

        # Older API: cge_modeling.solve_equations(model, **kwargs)
        from cge_modeling import solve_equations  # type: ignore
        return solve_equations(model, **kwargs)

    def _clone_model(self, model: Any) -> Any:
        """Return an independent copy of ``model`` for shock injection."""
        if hasattr(model, "copy"):
            return model.copy()
        from copy import deepcopy
        return deepcopy(model)

    @staticmethod
    def _scale_parameter(model: Any, name: str, factor: float) -> None:
        """Multiply a SAM parameter on the model by ``factor``.

        Tries the parameter-mutation paths cge_modeling supports across
        versions. Silently no-ops (with a warning) if no path applies.
        """
        # newer API: model.update_parameters({name: value}) or model.parameters[name]
        if hasattr(model, "parameters") and name in model.parameters:
            try:
                model.parameters[name] = model.parameters[name] * factor
                return
            except (TypeError, AttributeError):
                pass
        if hasattr(model, "update_parameters"):
            try:
                current = (
                    model.parameters[name]
                    if hasattr(model, "parameters") and name in model.parameters
                    else None
                )
                model.update_parameters(
                    {name: (current * factor) if current is not None else factor}
                )
                return
            except (TypeError, AttributeError, KeyError):
                pass
        if hasattr(model, "set_parameter"):
            try:
                model.set_parameter(name, factor, multiplicative=True)
                return
            except (TypeError, AttributeError):
                pass
        logger.warning(
            "PyCGE: could not apply shock to parameter %r — model API does not "
            "expose a recognised parameter setter. Shock ignored.", name,
        )

    def _standardize_outputs(
        self, baseline: Any, reform: Any,
    ) -> dict[str, Any]:
        """Compute pct-change-from-baseline for headline CGE aggregates.

        Looks for common cge_modeling result attributes / keys in this order:
        - ``.values`` / ``.x`` / ``.solution`` (mapping name -> value)
        - dict subscript access for keys: GDP, Y, C, w, r, EV
        Falls back to dumping whatever is available with raw_baseline /
        raw_reform tags so synthesis still has provenance.
        """
        b = self._extract_value_dict(baseline)
        r = self._extract_value_dict(reform)
        out: dict[str, Any] = {}

        for headline_var, std_key in (
            ("GDP", "gdp_impact_pct"),
            ("Y", "gdp_impact_pct"),
            ("C", "consumption_impact_pct"),
            ("w", "wage_impact_pct"),
            ("r", "interest_rate_impact_pct"),
            ("EV", "welfare_pct_change"),
        ):
            bv = b.get(headline_var)
            rv = r.get(headline_var)
            if bv is None or rv is None:
                continue
            try:
                bv, rv = float(bv), float(rv)
            except (TypeError, ValueError):
                continue
            if bv == 0:
                continue
            # Don't overwrite a value already populated from the first match.
            out.setdefault(std_key, round((rv - bv) / bv * 100.0, 4))

        # Also include sectoral output deltas where available.
        sector_b = self._extract_sectoral(b, "X")
        sector_r = self._extract_sectoral(r, "X")
        if sector_b and sector_r:
            sector_pct: dict[str, float] = {}
            for sector, base_val in sector_b.items():
                ref_val = sector_r.get(sector)
                if ref_val is None:
                    continue
                try:
                    base_f, ref_f = float(base_val), float(ref_val)
                except (TypeError, ValueError):
                    continue
                if base_f == 0:
                    continue
                sector_pct[sector] = round((ref_f - base_f) / base_f * 100.0, 4)
            if sector_pct:
                out["sectoral_output_pct_change"] = sector_pct

        # Carry diagnostic raw representations for provenance.
        out["raw_baseline"] = self._safe_truncate_dict(b)
        out["raw_reform"] = self._safe_truncate_dict(r)
        return out

    @staticmethod
    def _extract_value_dict(result: Any) -> dict[str, Any]:
        """Best-effort extract a {variable_name: value} dict from a result."""
        if result is None:
            return {}
        for attr in ("values", "x", "solution", "result"):
            v = getattr(result, attr, None)
            if isinstance(v, dict):
                return v
        if isinstance(result, dict):
            return result
        # Last resort: scan attributes.
        try:
            return {k: getattr(result, k) for k in dir(result)
                    if not k.startswith("_") and not callable(getattr(result, k))}
        except Exception:
            return {}

    @staticmethod
    def _extract_sectoral(d: dict[str, Any], key: str) -> dict[str, float]:
        v = d.get(key)
        if isinstance(v, dict):
            return v
        return {}

    @staticmethod
    def _safe_truncate_dict(d: dict[str, Any], max_items: int = 50) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(d.items()):
            if i >= max_items:
                out["_truncated_at"] = max_items
                break
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                out[str(k)] = repr(v)[:200]
        return out

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        if isinstance(raw, ModelOutput):
            return raw
        return ModelOutput(
            model_id=self.model_id,
            outputs=raw if isinstance(raw, dict) else {"raw": raw},
        )
