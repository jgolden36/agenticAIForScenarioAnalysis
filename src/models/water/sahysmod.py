"""Adapter for SahysMod — Spatially distributed agro-hydro-salinity model.

SahysMod simulates the coupled dynamics of soil salinity, groundwater depth, and
crop yield across spatially distributed irrigation districts. In the Hormuz pipeline
it captures the downstream agricultural consequences of reduced irrigation water
availability (caused by desalination disruption and disrupted fertiliser supply
logistics) and the associated secondary salinity accumulation in soils and
shallow aquifers.

Execution architecture
----------------------
The bundled distribution at ``Models/Water/SahysMod/SahysMod.exe`` is the ILRI
Windows binary (Oosterbaan et al.). It is a console application that reads an
input deck (``<name>.inp``) and writes three plain-text output files:

  * ``<name>.out`` — per-polygon, per-season, per-year block-structured records
                     containing salinity (Cw, Ci, Cd, Cqi, Cti) and groundwater
                     depth (Dw) values, separated by ``#`` markers.
  * ``<name>.gwt`` — groundwater flow records between connected nodes.
  * ``<name>.frq`` — cumulative frequency tables for soil salinity at the 20 /
                     40 / 60 / 80 percentile levels per node.

The adapter:

  1. Copies the baseline ``.inp`` into an isolated temp working directory.
  2. Optionally applies scenario shocks (irrigation water reduction and
     salinity scaling) by multiplying numeric values on configured line ranges
     in the deck.
  3. Invokes ``SahysMod.exe <deck>`` (or just ``SahysMod.exe`` and feeds the
     deck name on stdin — both invocation forms are tried) from the working
     directory.
  4. Parses the resulting ``.out``, ``.gwt`` and ``.frq`` files into a
     standardized ``ModelOutput``.

The line-range mutation strategy is intentionally conservative: SahysMod
``.inp`` files have a complex fixed-format structure where blocks of values
(rainfall, evapotranspiration, IaA / IaB / IaU irrigation, canal salinity,
etc.) appear as space-delimited streams whose lengths depend on
``NrOfInternalPoly`` and ``NrOfSeasons``. Without a full parser we cannot
unambiguously identify each block. The config therefore exposes
``irrigation_line_ranges`` and ``salinity_line_ranges`` so the user can point
the scaler at known IaA / Cic line ranges in their specific deck. If left
empty the deck is run unmodified and ``mutation_applied=False`` is recorded
in execution metadata so the synthesis layer knows the run was a baseline.

Real integration requirements
-----------------------------
* Windows host with ``SahysMod.exe`` available (``Models/Water/SahysMod/SahysMod.exe``).
* A pre-configured baseline ``.inp`` deck (the GARMSAR, ICMALD, ICMALDannual
  and HANSI sample decks bundled under ``Models/Water/SahysMod/`` are valid
  starting points).
* For meaningful mutation the user must enumerate which line ranges in their
  baseline deck correspond to irrigation and salinity inputs and put them in
  ``configs/model_configs/sahysmod.yaml``.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.common.types import AnalyticalLevel, CommoditySystem
from src.models.base import ModelAdapter, ModelOutput, ValidationResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parameter specifications
# ---------------------------------------------------------------------------

_REQUIRED_PARAMS: list[str] = [
    "irrigation_water_reduction_pct",
    "salinity_increase_factor",
    "disruption_duration_weeks",
]

_BOUNDS: dict[str, tuple[float, float]] = {
    "irrigation_water_reduction_pct": (0.0, 100.0),
    "salinity_increase_factor": (1.0, 20.0),
    "disruption_duration_weeks": (0.0, 260.0),
}


# Maas-Hoffmann salinity-yield relationship (used for derived relative crop
# yield). For a generic "moderately-tolerant" crop:
#   Y_rel = 1                               for ECe <= threshold
#   Y_rel = 1 - slope * (ECe - threshold)   for threshold < ECe < threshold + 100/slope
#   Y_rel = 0                               otherwise
# Threshold dS/m, slope = % yield loss per dS/m above threshold (converted to
# fractional units below).
_MAAS_HOFFMANN_THRESHOLD_DS_PER_M: float = 4.0
_MAAS_HOFFMANN_SLOPE_PCT_PER_DS_PER_M: float = 12.0
_SEVERE_SALINITY_THRESHOLD_DS_PER_M: float = 8.0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class LineRange(BaseModel):
    """Inclusive 0-indexed line range in a SahysMod .inp deck."""

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    def contains(self, line_no: int) -> bool:
        return self.start <= line_no <= self.end


class SahysModConfig(BaseModel):
    """Configuration for the SahysMod adapter."""

    model_config = {"protected_namespaces": ()}

    executable_path: Path = Field(
        description="Path to SahysMod.exe (or platform equivalent).",
    )
    baseline_input_deck: Path = Field(
        description=(
            "Path to a baseline SahysMod .inp deck (e.g. "
            "'Models/Water/SahysMod/GARMSAR/Garmsar.inp')."
        ),
    )
    timeout_seconds: int = Field(
        default=600,
        description="Maximum wall-clock seconds for a single SahysMod run.",
    )
    keep_working_copy: bool = Field(
        default=False,
        description=(
            "If True, do not delete the per-scenario working directory after "
            "execution. Useful for debugging."
        ),
    )
    irrigation_line_ranges: list[LineRange] = Field(
        default_factory=list,
        description=(
            "0-indexed inclusive line ranges in the baseline deck that contain "
            "irrigation water inputs (IaA / IaB / IaU blocks). Numeric values "
            "on these lines are multiplied by (1 - irrigation_water_reduction_pct/100) "
            "for the scaled simulation period."
        ),
    )
    salinity_line_ranges: list[LineRange] = Field(
        default_factory=list,
        description=(
            "0-indexed inclusive line ranges in the baseline deck that contain "
            "initial salinity values (Cti / Cqi / Cic blocks). Numeric values "
            "on these lines are multiplied by salinity_increase_factor."
        ),
    )
    cli_invocation: str = Field(
        default="positional",
        description=(
            "How SahysMod.exe accepts the input deck name. 'positional' passes "
            "the deck as argv[1]; 'stdin' writes the deck name to stdin."
        ),
    )
    sentinel_min: float = Field(
        default=-2.0,
        description=(
            "Numeric values <= this sentinel are not scaled (e.g. -1 placeholders "
            "in the SahysMod fixed-format deck)."
        ),
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class SahysModAdapter(ModelAdapter):
    """Adapter for the SahysMod agro-hydro-salinity model."""

    def __init__(self, config: SahysModConfig | None = None) -> None:
        self._config = config

    # -- Identity properties ------------------------------------------------

    @property
    def model_id(self) -> str:
        return "sahysmod"

    @property
    def commodity_system(self) -> CommoditySystem:
        return CommoditySystem.WATER

    @property
    def analytical_level(self) -> AnalyticalLevel:
        return AnalyticalLevel.COMMODITY

    @property
    def description(self) -> str:
        return (
            "SahysMod: Spatially distributed agro-hydro-salinity model. Simulates "
            "the impact of reduced irrigation water availability on soil salinity, "
            "groundwater depth, and relative crop yield across Gulf and Near-East "
            "irrigation districts under Strait of Hormuz closure scenarios."
        )

    # -- Validation ---------------------------------------------------------

    def validate_inputs(self, params: dict[str, Any]) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        for name in _REQUIRED_PARAMS:
            if name not in params:
                errors.append(f"Missing required parameter: '{name}'")

        for param_name, (lo, hi) in _BOUNDS.items():
            if param_name not in params:
                continue
            value = params[param_name]
            try:
                fval = float(value)
            except (TypeError, ValueError):
                errors.append(
                    f"Parameter '{param_name}' must be numeric; got {value!r}"
                )
                continue
            if not (lo <= fval <= hi):
                warnings.append(
                    f"Parameter '{param_name}' value {fval} is outside expected "
                    f"range [{lo}, {hi}]; verify before running."
                )

        if "salinity_increase_factor" in params:
            try:
                factor = float(params["salinity_increase_factor"])
                if factor < 1.0:
                    errors.append(
                        "Parameter 'salinity_increase_factor' must be >= 1.0 "
                        "(a factor < 1 implies salinity improvement, which is "
                        "inconsistent with a supply disruption scenario)."
                    )
            except (TypeError, ValueError):
                pass

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- Input translation --------------------------------------------------

    def translate_inputs(self, params: dict[str, Any]) -> dict[str, Any]:
        """Apply scenario shocks to the baseline deck and return a dict that
        ``execute()`` consumes.

        If no config is set or no line ranges are configured, the deck is
        passed through unmodified and ``mutation_applied=False`` is set so the
        executor records this in metadata.
        """
        scenario_id = str(params.get("scenario_id", "default"))

        deck_path: Path | None = None
        baseline_text = ""
        n_internal_poly: int | None = None
        n_seasons: int | None = None
        n_years: int | None = None

        if self._config is not None:
            deck_path = self._config.baseline_input_deck
            if deck_path.is_file():
                baseline_text = deck_path.read_text(encoding="utf-8", errors="replace")
                header = self._parse_header(baseline_text)
                n_years = header.get("n_years")
                n_seasons = header.get("n_seasons")
                n_internal_poly = header.get("n_internal_poly")

        irrigation_factor = 1.0 - float(params.get("irrigation_water_reduction_pct", 0.0)) / 100.0
        salinity_factor = float(params.get("salinity_increase_factor", 1.0))

        modified_text = baseline_text
        mutation_applied = False
        mutation_summary: dict[str, Any] = {
            "irrigation_factor": irrigation_factor,
            "salinity_factor": salinity_factor,
            "irrigation_lines_scaled": 0,
            "salinity_lines_scaled": 0,
        }

        if (
            self._config is not None
            and baseline_text
            and (self._config.irrigation_line_ranges or self._config.salinity_line_ranges)
        ):
            modified_text, scaled_counts = self._apply_line_scaling(
                baseline_text,
                irrigation_ranges=self._config.irrigation_line_ranges,
                irrigation_factor=irrigation_factor,
                salinity_ranges=self._config.salinity_line_ranges,
                salinity_factor=salinity_factor,
                sentinel_min=self._config.sentinel_min,
            )
            mutation_applied = True
            mutation_summary["irrigation_lines_scaled"] = scaled_counts["irrigation"]
            mutation_summary["salinity_lines_scaled"] = scaled_counts["salinity"]

        return {
            "scenario_id": scenario_id,
            "modified_deck_text": modified_text,
            "deck_basename": (deck_path.stem if deck_path is not None else "scenario"),
            "n_years": n_years,
            "n_seasons": n_seasons,
            "n_internal_poly": n_internal_poly,
            "mutation_applied": mutation_applied,
            "mutation_summary": mutation_summary,
            "params_in": dict(params),
        }

    # -- Execution ----------------------------------------------------------

    def execute(self, inputs: Any) -> ModelOutput:
        """Run SahysMod against the (possibly mutated) deck in an isolated dir."""
        if self._config is None:
            raise NotImplementedError(
                "SahysModAdapter.execute() requires a SahysModConfig. To "
                "integrate SahysMod:\n"
                "  1. Configure 'executable_path' and 'baseline_input_deck' in "
                "configs/model_configs/sahysmod.yaml.\n"
                "  2. (Optional) Set 'irrigation_line_ranges' and "
                "'salinity_line_ranges' to point the mutator at the IaA / Cic "
                "blocks in your baseline deck.\n"
                "  3. Re-build the registry via build_default_registry("
                "config_dir='configs/model_configs')."
            )

        if not isinstance(inputs, dict):
            raise TypeError(
                f"SahysMod inputs must be a dict from translate_inputs(); got {type(inputs)}"
            )

        config = self._config
        self._validate_prerequisites(config)

        scenario_id = str(inputs.get("scenario_id", "default"))
        deck_basename = inputs.get("deck_basename") or "scenario"
        # SahysMod is sensitive to long names; clamp to 24 chars and strip non-alnum.
        safe_name = re.sub(r"[^A-Za-z0-9_]", "_", f"{deck_basename}_{scenario_id}")[:24]

        work_dir = Path(tempfile.mkdtemp(prefix=f"sahysmod_{scenario_id}_"))
        try:
            deck_filename = f"{safe_name}.inp"
            deck_path = work_dir / deck_filename
            deck_path.write_text(inputs["modified_deck_text"], encoding="utf-8")

            t_start = time.time()
            run_result = self._run_sahysmod(config, work_dir, deck_filename)
            elapsed = time.time() - t_start

            out_path = work_dir / f"{safe_name}.out"
            gwt_path = work_dir / f"{safe_name}.gwt"
            frq_path = work_dir / f"{safe_name}.frq"

            if not out_path.exists():
                produced = sorted(p.name for p in work_dir.iterdir())
                raise FileNotFoundError(
                    f"SahysMod did not produce expected output {out_path.name}. "
                    f"Files in work dir: {produced}. "
                    f"stdout tail: {run_result.stdout[-1000:] if run_result.stdout else ''}"
                )

            raw = {
                "scenario_id": scenario_id,
                "out_path": str(out_path),
                "gwt_path": str(gwt_path) if gwt_path.exists() else None,
                "frq_path": str(frq_path) if frq_path.exists() else None,
                "out_text": out_path.read_text(encoding="utf-8", errors="replace"),
                "gwt_text": gwt_path.read_text(encoding="utf-8", errors="replace")
                if gwt_path.exists() else "",
                "frq_text": frq_path.read_text(encoding="utf-8", errors="replace")
                if frq_path.exists() else "",
            }

            output = self.parse_outputs(raw)
            output.metadata.update({
                "scenario_id": scenario_id,
                "params_in": inputs.get("params_in", {}),
                "mutation_applied": inputs.get("mutation_applied", False),
                "mutation_summary": inputs.get("mutation_summary", {}),
                "n_years": inputs.get("n_years"),
                "n_seasons": inputs.get("n_seasons"),
                "n_internal_poly": inputs.get("n_internal_poly"),
                "work_dir": str(work_dir),
                "elapsed_seconds": round(elapsed, 2),
                "sahysmod_returncode": run_result.returncode,
                "stdout_tail": run_result.stdout[-2000:] if run_result.stdout else "",
                "stderr_tail": run_result.stderr[-2000:] if run_result.stderr else "",
            })
            return output

        finally:
            if not config.keep_working_copy:
                shutil.rmtree(work_dir, ignore_errors=True)

    # -- Output parsing -----------------------------------------------------

    def parse_outputs(self, raw: Any) -> ModelOutput:
        """Parse SahysMod ``.out``, ``.gwt`` and ``.frq`` text into standardized
        per-polygon, per-(year, season) dicts.

        Output keys:
            * ``soil_salinity_dS_m``  : ``Cw``  (root-zone soil-water salinity)
            * ``incoming_salinity_dS_m`` : ``Ci`` (incoming irrigation salinity)
            * ``drain_salinity_dS_m`` : ``Cd``
            * ``aquifer_salinity_dS_m`` : ``Cqi``
            * ``groundwater_depth_m`` : ``Dw``
            * ``relative_crop_yield`` : derived via Maas-Hoffmann from Cw
            * ``frequency_table``     : 20/40/60/80 percentile salinities by node
            * ``affected_polygons``   : nodes where Cw > severe threshold in any season

        Time dimension: results are keyed by ``"y{year}_s{season}"`` strings.
        """
        if not isinstance(raw, dict):
            raw = {"out_text": str(raw)}

        out_text: str = raw.get("out_text", "") or ""
        gwt_text: str = raw.get("gwt_text", "") or ""
        frq_text: str = raw.get("frq_text", "") or ""

        per_polygon = self._parse_out_text(out_text)

        # Build standardized dicts: {polygon_id: {time_key: value}}
        soil_salinity: dict[str, dict[str, float]] = {}
        incoming_salinity: dict[str, dict[str, float]] = {}
        drain_salinity: dict[str, dict[str, float]] = {}
        aquifer_salinity: dict[str, dict[str, float]] = {}
        groundwater_depth: dict[str, dict[str, float]] = {}
        relative_yield: dict[str, dict[str, float]] = {}
        time_keys: set[str] = set()
        affected_polygons: set[str] = set()

        for record in per_polygon:
            poly_id = str(record["polygon"])
            time_key = f"y{record['year']}_s{record['season']}"
            time_keys.add(time_key)

            cw = record["values"].get("Cw")
            ci = record["values"].get("Ci")
            cd = record["values"].get("Cd")
            cqi = record["values"].get("Cqi")
            dw = record["values"].get("Dw")

            if cw is not None:
                soil_salinity.setdefault(poly_id, {})[time_key] = cw
                if cw > _SEVERE_SALINITY_THRESHOLD_DS_PER_M:
                    affected_polygons.add(poly_id)
                relative_yield.setdefault(poly_id, {})[time_key] = (
                    self._maas_hoffmann_yield(cw)
                )
            if ci is not None:
                incoming_salinity.setdefault(poly_id, {})[time_key] = ci
            if cd is not None:
                drain_salinity.setdefault(poly_id, {})[time_key] = cd
            if cqi is not None:
                aquifer_salinity.setdefault(poly_id, {})[time_key] = cqi
            if dw is not None:
                groundwater_depth.setdefault(poly_id, {})[time_key] = dw

        frequency_table = self._parse_frq_text(frq_text)
        groundwater_flows = self._parse_gwt_text(gwt_text)

        return ModelOutput(
            model_id=self.model_id,
            convergence_status="completed",
            outputs={
                "soil_salinity_dS_m": soil_salinity,
                "incoming_salinity_dS_m": incoming_salinity,
                "drain_salinity_dS_m": drain_salinity,
                "aquifer_salinity_dS_m": aquifer_salinity,
                "groundwater_depth_m": groundwater_depth,
                "relative_crop_yield": relative_yield,
                "frequency_table": frequency_table,
                "groundwater_flows_m3_per_season": groundwater_flows,
                "time_keys": sorted(time_keys),
                "affected_polygons": sorted(
                    affected_polygons, key=lambda x: int(x) if x.isdigit() else 0
                ),
                "n_records_parsed": len(per_polygon),
            },
            metadata={
                "unit_notes": {
                    "soil_salinity_dS_m": "Cw, dS/m (electrical conductivity)",
                    "incoming_salinity_dS_m": "Ci, dS/m",
                    "drain_salinity_dS_m": "Cd, dS/m",
                    "aquifer_salinity_dS_m": "Cqi, dS/m",
                    "groundwater_depth_m": "Dw, depth below surface (m)",
                    "relative_crop_yield": (
                        f"Derived via Maas-Hoffmann (threshold "
                        f"{_MAAS_HOFFMANN_THRESHOLD_DS_PER_M} dS/m, slope "
                        f"{_MAAS_HOFFMANN_SLOPE_PCT_PER_DS_PER_M}% per dS/m). "
                        f"Fraction of potential, 0-1."
                    ),
                    "groundwater_flows_m3_per_season": (
                        "Flow between connected nodes, m3/season"
                    ),
                    "frequency_table": (
                        "20/40/60/80 percentile cumulative frequency soil salinity "
                        "by node, dS/m"
                    ),
                    "severe_salinity_threshold": (
                        f"{_SEVERE_SALINITY_THRESHOLD_DS_PER_M} dS/m (used for "
                        f"affected_polygons flag)"
                    ),
                },
            },
        )

    # ======================================================================
    # Private helpers
    # ======================================================================

    def _validate_prerequisites(self, config: SahysModConfig) -> None:
        if not config.executable_path.is_file():
            raise FileNotFoundError(
                f"SahysMod executable not found: {config.executable_path}. "
                "Set 'executable_path' in configs/model_configs/sahysmod.yaml."
            )
        if not config.baseline_input_deck.is_file():
            raise FileNotFoundError(
                f"SahysMod baseline input deck not found: {config.baseline_input_deck}. "
                "Set 'baseline_input_deck' in configs/model_configs/sahysmod.yaml."
            )

    @staticmethod
    def _parse_header(deck_text: str) -> dict[str, int | None]:
        """Parse the first non-blank numeric lines of the deck.

        Layout of the first three numeric lines is:
            line A:  NrOfYears  NrOfSeasons  CalcIndex  MaxYears
            line B:  season durations (floats)
            line C:  TotPoly  InternalPoly  ExternalPoly  Scale
        """
        result: dict[str, int | None] = {
            "n_years": None,
            "n_seasons": None,
            "n_internal_poly": None,
            "n_total_poly": None,
        }

        numeric_re = re.compile(r"^[\s\d\.\-eE]+$")
        first_numeric: list[list[float]] = []
        for line in deck_text.splitlines():
            stripped = line.strip()
            if not stripped or not numeric_re.match(stripped):
                continue
            try:
                tokens = [float(t) for t in stripped.split()]
            except ValueError:
                continue
            first_numeric.append(tokens)
            if len(first_numeric) >= 3:
                break

        if len(first_numeric) >= 1 and len(first_numeric[0]) >= 2:
            result["n_years"] = int(first_numeric[0][0])
            result["n_seasons"] = int(first_numeric[0][1])

        if len(first_numeric) >= 3 and len(first_numeric[2]) >= 2:
            result["n_total_poly"] = int(first_numeric[2][0])
            result["n_internal_poly"] = int(first_numeric[2][1])

        return result

    @staticmethod
    def _apply_line_scaling(
        text: str,
        *,
        irrigation_ranges: list[LineRange],
        irrigation_factor: float,
        salinity_ranges: list[LineRange],
        salinity_factor: float,
        sentinel_min: float,
    ) -> tuple[str, dict[str, int]]:
        """Multiply numeric tokens on configured line ranges.

        Returns the modified text plus a count of how many lines were scaled
        for each category. Tokens whose value is <= ``sentinel_min`` are left
        untouched (they're SahysMod's ``-1`` placeholders).
        """
        token_re = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
        scaled = {"irrigation": 0, "salinity": 0}

        def scale_line(line: str, factor: float) -> str:
            def repl(m: re.Match[str]) -> str:
                try:
                    val = float(m.group(0))
                except ValueError:
                    return m.group(0)
                if val <= sentinel_min:
                    return m.group(0)
                new_val = val * factor
                if "." in m.group(0) or "e" in m.group(0).lower():
                    width = len(m.group(0))
                    formatted = f"{new_val:.4f}"
                    return formatted if len(formatted) >= width else formatted.rjust(width)
                return f"{new_val:.4f}"
            return token_re.sub(repl, line)

        out_lines: list[str] = []
        for idx, line in enumerate(text.splitlines()):
            if any(rng.contains(idx) for rng in irrigation_ranges):
                out_lines.append(scale_line(line, irrigation_factor))
                scaled["irrigation"] += 1
            elif any(rng.contains(idx) for rng in salinity_ranges):
                out_lines.append(scale_line(line, salinity_factor))
                scaled["salinity"] += 1
            else:
                out_lines.append(line)

        # Preserve trailing newline if original had one
        result = "\n".join(out_lines)
        if text.endswith("\n"):
            result += "\n"
        return result, scaled

    def _run_sahysmod(
        self,
        config: SahysModConfig,
        work_dir: Path,
        deck_filename: str,
    ) -> subprocess.CompletedProcess[str]:
        """Run SahysMod with stdin or positional invocation."""
        executable = str(config.executable_path)

        if config.cli_invocation == "positional":
            cmd = [executable, deck_filename]
            stdin_data: str | None = None
        else:
            cmd = [executable]
            stdin_data = f"{deck_filename}\n"

        logger.info("Running SahysMod: %s (cwd=%s)", " ".join(cmd), work_dir)
        try:
            return subprocess.run(
                cmd,
                cwd=str(work_dir),
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"SahysMod timed out after {config.timeout_seconds}s in {work_dir}."
            ) from exc

    @staticmethod
    def _parse_out_text(out_text: str) -> list[dict[str, Any]]:
        """Parse the per-polygon, per-season blocks from a ``.out`` file.

        Each block is delimited by ``#`` and contains a header like:

            YEAR:    <Y>    Name of output file: ...
            ************
            Season:  <S>    Duration: ... months.
            ************
            Polygon: <P>    X (cm): ... Y (cm): ...
            <key = value pairs over several lines>

        Returns a list of records ``{year, season, polygon, values: dict}``.
        Values that print as ``-`` (missing/not applicable) are omitted.
        """
        records: list[dict[str, Any]] = []
        if not out_text:
            return records

        # Split blocks by the '#' separator, but discard the header preamble
        # (everything before the first 'YEAR:' line).
        first_year_idx = out_text.find("YEAR:")
        if first_year_idx < 0:
            return records
        body = out_text[first_year_idx:]
        blocks = body.split("\n#")

        year_re = re.compile(r"YEAR:\s*(\d+)")
        season_re = re.compile(r"Season:\s*(\d+)")
        poly_re = re.compile(r"Polygon:\s*(\d+)")
        # Match "Name = value" with value as either a number or '-'
        kv_re = re.compile(
            r"\b([A-Za-z][A-Za-z0-9_*]*)\s*=\s*"
            r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|-)"
        )

        for block in blocks:
            year_m = year_re.search(block)
            season_m = season_re.search(block)
            poly_m = poly_re.search(block)
            if not (year_m and season_m and poly_m):
                continue

            values: dict[str, float] = {}
            for kv in kv_re.finditer(block):
                key = kv.group(1)
                raw_val = kv.group(2)
                if raw_val == "-":
                    continue
                # Skip the polygon / season / year captures themselves
                if key in ("YEAR", "Season", "Polygon"):
                    continue
                try:
                    values[key] = float(raw_val)
                except ValueError:
                    continue

            records.append({
                "year": int(year_m.group(1)),
                "season": int(season_m.group(1)),
                "polygon": int(poly_m.group(1)),
                "values": values,
            })

        return records

    @staticmethod
    def _parse_frq_text(frq_text: str) -> dict[str, list[dict[str, Any]]]:
        """Parse the cumulative frequency table from a ``.frq`` file.

        Returns ``{time_key: [{salinity_type, node, p20, p40, p60, p80}, ...]}``.
        """
        result: dict[str, list[dict[str, Any]]] = {}
        if not frq_text:
            return result

        current_year: int | None = None
        current_season: int | None = None
        year_re = re.compile(r"YEAR:\s*(\d+)")
        season_re = re.compile(r"Season:\s*(\d+)")
        # e.g.  "Cr4 in NODE"   1  2.66E+000 4.41E+000 6.24E+000 8.82E+000
        row_re = re.compile(
            r'"([^"]+) in NODE"\s+(\d+)\s+'
            r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
            r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
            r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
            r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
        )

        for line in frq_text.splitlines():
            ym = year_re.search(line)
            if ym:
                current_year = int(ym.group(1))
                continue
            sm = season_re.search(line)
            if sm:
                current_season = int(sm.group(1))
                continue
            rm = row_re.search(line)
            if rm and current_year is not None and current_season is not None:
                key = f"y{current_year}_s{current_season}"
                result.setdefault(key, []).append({
                    "salinity_type": rm.group(1),
                    "node": int(rm.group(2)),
                    "p20": float(rm.group(3)),
                    "p40": float(rm.group(4)),
                    "p60": float(rm.group(5)),
                    "p80": float(rm.group(6)),
                })

        return result

    @staticmethod
    def _parse_gwt_text(gwt_text: str) -> dict[str, list[dict[str, Any]]]:
        """Parse the groundwater flow records from a ``.gwt`` file.

        Returns ``{time_key: [{from_node, to_nodes: [...], flows_m3_season: [...]}]}``.
        """
        result: dict[str, list[dict[str, Any]]] = {}
        if not gwt_text:
            return result

        current_year: int | None = None
        current_season: int | None = None
        year_re = re.compile(r"YEAR:\s*(\d+)")
        season_re = re.compile(r"Season:\s*(\d+)")
        from_re = re.compile(r'"from node"\s+(\d+)')
        # captures the "to node" line and the flows line which follows it
        to_re = re.compile(r'"to node:"((?:\s+\d+)+)')
        flows_re = re.compile(
            r"^\s*-\s+-\s+-\s+((?:\s+-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)+)"
        )

        lines = gwt_text.splitlines()
        i = 0
        pending_from: int | None = None
        pending_tos: list[int] = []
        while i < len(lines):
            line = lines[i]
            ym = year_re.search(line)
            if ym:
                current_year = int(ym.group(1))
                i += 1
                continue
            sm = season_re.search(line)
            if sm:
                current_season = int(sm.group(1))
                i += 1
                continue
            fm = from_re.search(line)
            if fm:
                pending_from = int(fm.group(1))
                pending_tos = []
                i += 1
                continue
            tm = to_re.search(line)
            if tm:
                pending_tos = [int(x) for x in tm.group(1).split()]
                i += 1
                continue
            flm = flows_re.search(line)
            if (
                flm
                and pending_from is not None
                and pending_tos
                and current_year is not None
                and current_season is not None
            ):
                flows = [float(x) for x in flm.group(1).split()]
                key = f"y{current_year}_s{current_season}"
                result.setdefault(key, []).append({
                    "from_node": pending_from,
                    "to_nodes": pending_tos,
                    "flows_m3_per_season": flows,
                })
                pending_from = None
                pending_tos = []
            i += 1

        return result

    @staticmethod
    def _maas_hoffmann_yield(ece_ds_m: float) -> float:
        """Derive relative crop yield from soil salinity via Maas-Hoffmann."""
        threshold = _MAAS_HOFFMANN_THRESHOLD_DS_PER_M
        slope_frac = _MAAS_HOFFMANN_SLOPE_PCT_PER_DS_PER_M / 100.0
        if ece_ds_m <= threshold:
            return 1.0
        loss = slope_frac * (ece_ds_m - threshold)
        return max(0.0, 1.0 - loss)
