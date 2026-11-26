#!/usr/bin/env python3
"""APSIM-GTAP coupled driver for the Hormuz pipeline.

Runs in the AgResilience environment (``agres`` conda env), NOT in the
pipeline's environment. Both repositories have a top-level ``src`` package,
so this script never imports the pipeline's ``src``; the adapter
(``src/models/fertilizer/apsim_gtap.py``) launches it as a subprocess with
the AgResilience checkout as the working directory and passes everything it
needs in ``inputs.json``.

What it does (port of AgResilience ``src/experiments/fixed_point.py``):

1. E0 gate: one GTAP solve with no shocks; the GDP residual must be ~0.
2. Builds the Hormuz shock as declarative GTAP instructions:
   * ``production_shock chm/wasia``      x (1 - fertilizer loss share)
   * ``production_shock extract/wasia``  x (1 - oil loss share)
   * optional ``tms`` trade wedge on chm and extract imports from wasia
     into every other region: 1 + (rerouting multiplier - 1) x freight share
   (all already annualised by the adapter).
3. Iterates GTAP <-> APSIM emulator to a fixed point: US chemicals
   consumption change -> field nitrogen (``coupling.consumption_to_nitrogen``)
   -> emulator maize yield -> ``production_shock gro/usa`` = yield ratio ->
   re-solve, until the yield ratio stops changing. Arm A (first pass, the
   open loop) and arm C (fixed point) are both reported.

GTAP solves go through AgResilience's content-addressed cache; the Julia
server (``src/tools/gtap_server.jl``) is started only on the first cache
miss and always stopped on exit.

    python apsim_gtap_driver.py --in inputs.json --out outputs.json
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPORT = [{"variable": v} for v in (
    "gdp_change", "consumption_change", "price_change",
    "production_change", "imports_change",
)]
GULF_REGION = "wasia"
US_REGION = "usa"
E0_TOLERANCE_PCT = 1e-4


# ----------------------------------------------------------------- requests

def shock_instructions(shocks: dict[str, Any], regions: list[str] | None) -> list[dict]:
    """Declarative GTAP instructions for the Hormuz shock (no crop feedback).

    ``shocks`` holds already-annualised fractions/multipliers computed by the
    adapter: ``chm_output_loss_share``, ``extract_output_loss_share``,
    ``trade_wedge`` (tms multiplier, 1.0 = none), ``gulf_region``.
    ``regions`` is the model's region list (needed only for the wedge).
    """
    gulf = shocks.get("gulf_region", GULF_REGION)
    apply: list[dict] = []
    for comm, key in (("chm", "chm_output_loss_share"), ("extract", "extract_output_loss_share")):
        share = float(shocks.get(key, 0.0) or 0.0)
        if share > 0.0:
            apply.append({
                "variable": "production_shock",
                "indices": {"commodity": comm, "region": gulf},
                "operation": "multiply", "value": round(1.0 - share, 8),
            })
    wedge = float(shocks.get("trade_wedge", 1.0) or 1.0)
    if wedge != 1.0:
        if not regions:
            raise ValueError("trade wedge requested but the GTAP region list is unknown")
        for comm in ("chm", "extract"):
            for dest in regions:
                if dest == gulf:
                    continue
                apply.append({
                    "variable": "tms",
                    "indices": {"commodity": comm, "region_from": gulf, "region_to": dest},
                    "operation": "multiply", "value": round(wedge, 8),
                })
    return apply


def make_request(base_apply: list[dict], productivity: float,
                 parameters: list[dict] | None = None) -> dict:
    """One comparative-static request; ``productivity`` is the US grain yield ratio."""
    apply = list(base_apply)
    if productivity != 1.0:
        apply.append({"variable": "production_shock",
                      "indices": {"commodity": "gro", "region": US_REGION},
                      "operation": "multiply", "value": round(productivity, 10)})
    req: dict[str, Any] = {"mode": "declarative", "apply": apply, "report": REPORT}
    if parameters:
        req["parameters"] = parameters
    return req


# ----------------------------------------------------------------- results

def economics(result: dict, extract: Callable[..., float | None]) -> dict[str, float | None]:
    return {
        "us_gdp_pct": extract(result, "gdp_change", region=US_REGION),
        "us_chm_consumption_pct": extract(result, "consumption_change", region=US_REGION, commodity="chm"),
        "us_gro_price_pct": extract(result, "price_change", region=US_REGION, commodity="gro"),
        "us_gro_production_pct": extract(result, "production_change", region=US_REGION, commodity="gro"),
    }


def by_region(result: dict, extract: Callable[..., float | None], variable: str,
              commodity: str | None = None) -> dict[str, float | None]:
    regions = [str(r) for r in (result.get("regions") or [])]
    out: dict[str, float | None] = {}
    for r in regions:
        if commodity is None:
            out[r] = extract(result, variable, region=r)
        else:
            out[r] = extract(result, variable, region=r, commodity=commodity)
    return out


def run_fixed_point(
    solve: Callable[[dict], dict],
    extract: Callable[..., float | None],
    yield_at: Callable[[float], float],
    to_nitrogen: Callable[[float, float, float], float],
    base_apply: list[dict],
    baseline_n: float,
    coupling_elasticity: float = 1.0,
    parameters: list[dict] | None = None,
    max_iter: int = 12,
    tol_pct: float = 1e-6,
) -> dict[str, Any]:
    """GTAP <-> crop fixed point (AgResilience fixed_point.run_case, Hormuz shock)."""
    y0 = yield_at(baseline_n)
    if not (isinstance(y0, (int, float)) and math.isfinite(y0) and y0 > 0):
        raise ValueError(f"baseline yield must be positive and finite, got {y0!r}")
    productivity = 1.0
    trace: list[dict[str, Any]] = []
    converged = False
    last_result: dict | None = None
    for k in range(max_iter):
        last_result = solve(make_request(base_apply, productivity, parameters))
        econ = economics(last_result, extract)
        chm = econ["us_chm_consumption_pct"]
        if chm is None or not math.isfinite(chm):
            raise ValueError("GTAP result has no US chemicals consumption change")
        n = to_nitrogen(chm, baseline_n, coupling_elasticity)
        ratio = yield_at(n) / y0
        if not math.isfinite(ratio):
            raise ValueError("non-finite yield ratio in fixed-point iteration")
        trace.append({"iteration": k, "productivity_in": productivity,
                      "nitrogen_kg_ha": n, "yield_change_pct": 100.0 * (ratio - 1.0), **econ})
        if abs(100.0 * (ratio - productivity)) <= tol_pct:
            converged = True
            break
        productivity = ratio
    arm_a, arm_c = trace[0], trace[-1]
    gap = {}
    for key in ("yield_change_pct", "us_gro_price_pct", "us_gro_production_pct", "us_gdp_pct"):
        a, c = arm_a.get(key), arm_c.get(key)
        gap[key] = (c - a) if a is not None and c is not None else None
    return {"converged": converged, "iterations": len(trace), "baseline_yield_g_m2": y0,
            "arm_a": arm_a, "arm_c": arm_c, "trace": trace, "open_loop_gap": gap,
            "final_result": last_result}


def assemble_outputs(fp: dict[str, Any], zero: dict[str, Any], baseline_n: float,
                     extract: Callable[..., float | None]) -> dict[str, Any]:
    final = fp["final_result"] or {}
    arm_c = fp["arm_c"]
    zero_gdp = [v for v in by_region(zero, extract, "gdp_change").values() if v is not None]
    residual = max((abs(v) for v in zero_gdp), default=None)
    n = arm_c["nitrogen_kg_ha"]
    trace = [{k: v for k, v in row.items()} for row in fp["trace"]]
    return {
        "us_gdp_pct": arm_c["us_gdp_pct"],
        "us_maize_yield_change_pct": arm_c["yield_change_pct"],
        "us_nitrogen_kg_ha": n,
        "us_nitrogen_change_pct": 100.0 * (n / baseline_n - 1.0) if baseline_n else None,
        "us_chm_consumption_pct": arm_c["us_chm_consumption_pct"],
        "us_gro_price_pct": arm_c["us_gro_price_pct"],
        "us_gro_production_pct": arm_c["us_gro_production_pct"],
        "gulf_gdp_pct": extract(final, "gdp_change", region=GULF_REGION),
        "gdp_change_by_region": by_region(final, extract, "gdp_change"),
        "gro_price_pct_by_region": by_region(final, extract, "price_change", "gro"),
        "food_price_pct_by_region": by_region(final, extract, "price_change", "food"),
        "chm_price_pct_by_region": by_region(final, extract, "price_change", "chm"),
        "gro_production_pct_by_region": by_region(final, extract, "production_change", "gro"),
        "fixed_point_iterations": fp["iterations"],
        "converged": fp["converged"],
        "arm_a": fp["arm_a"],
        "arm_c": arm_c,
        "open_loop_gap": fp["open_loop_gap"],
        "fixed_point_trace": trace,
        "baseline_yield_g_m2": fp["baseline_yield_g_m2"],
        "zero_shock_residual_gdp_pct": residual,
        "zero_shock_gate_passed": residual is not None and residual <= E0_TOLERANCE_PCT,
    }


# ----------------------------------------------------------------- server

def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class GTAPServer:
    """Starts ``gtap_server.jl`` on first use; always stopped by ``close``."""

    def __init__(self, cfg: dict[str, Any], log_path: Path) -> None:
        self.cfg = cfg
        self.log_path = log_path
        self.proc: subprocess.Popen | None = None
        self.url: str | None = None

    def ensure(self) -> str:
        if self.url is not None:
            return self.url
        port = _free_port()
        root = Path(self.cfg["agres_root"])
        env = {**os.environ, **{k: str(v) for k, v in (self.cfg.get("server_env") or {}).items()},
               "GTAP_SERVE": "1", "GTAP_HOST": "127.0.0.1", "GTAP_PORT": str(port)}
        if self.cfg.get("gtap_calib_file"):
            env["GTAP_CALIB_FILE"] = str(self.cfg["gtap_calib_file"])
        cmd = [self.cfg.get("julia_executable", "julia"), f"--project={root}",
               str(root / "src" / "tools" / "gtap_server.jl")]
        self._log = open(self.log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(cmd, cwd=str(root), env=env,
                                     stdout=self._log, stderr=subprocess.STDOUT)
        deadline = time.time() + float(self.cfg.get("server_startup_timeout_s", 1800))
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(f"GTAP server exited during startup (rc={self.proc.returncode}); see {self.log_path}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=2):
                    self.url = f"http://127.0.0.1:{port}"
                    return self.url
            except OSError:
                time.sleep(5)
        raise TimeoutError(f"GTAP server did not start within the timeout; see {self.log_path}")

    def close(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if getattr(self, "_log", None):
            self._log.close()


# ----------------------------------------------------------------- main

def _import_agres(root: Path):
    """Put the AgResilience checkout first on sys.path and import its pieces."""
    here = str(Path(__file__).resolve().parent)
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve().as_posix() != Path(here).as_posix()]
    sys.path.insert(0, str(root))
    from src.experiments import coupling  # type: ignore
    from src.experiments import fixed_point  # type: ignore
    from src.experiments.cache import Cache  # type: ignore
    from src.experiments.viz.gtap_results import extract_metric  # type: ignore
    return coupling, fixed_point, Cache, extract_metric


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--in", dest="inp", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)

    data = json.loads(args.inp.read_text(encoding="utf-8"))
    cfg = data["config"]
    root = Path(cfg["agres_root"]).resolve()
    os.chdir(root)
    if cfg.get("cache_dir"):
        os.environ["AGRES_CACHE_DIR"] = str(cfg["cache_dir"])
    os.environ["AGRES_CALIB_ID"] = str(cfg.get("calib_id", "default"))
    # AgResilience caches default to cache_only (a miss raises); this driver
    # solves new shocks, so read and write. Scalers are never re-exported.
    os.environ["GTAP_CACHE_MODE"] = "read_write"
    os.environ.setdefault("APSIM_CACHE_MODE", "read_write")
    os.environ.setdefault("APSIM_SCALER_AUTOEXPORT", "0")
    os.environ["PYTHONPATH"] = str(root)

    coupling, fixed_point, Cache, extract_metric = _import_agres(root)
    cache = Cache("gtap", calib_id=os.environ["AGRES_CALIB_ID"])
    server = GTAPServer(cfg, args.out.parent / "gtap_server.log")
    n_solves = {"cache_hits": 0, "solves": 0}

    def solve(req: dict) -> dict:
        hit = cache.get(req)
        if hit is not None:
            n_solves["cache_hits"] += 1
            return hit
        os.environ["GTAP_URL"] = server.ensure()
        n_solves["solves"] += 1
        return fixed_point.gtap_solve(req)

    try:
        if "cases" in data:
            # Batch mode (Armington-elasticity sweep): one server for every
            # case; cases sharing gtap_parameter_edits share one re-calibration,
            # so callers should group them by draw.
            results = []
            for case in data["cases"]:
                try:
                    out = run_case(case, solve, coupling, fixed_point, extract_metric, n_solves)
                    results.append({"case_id": case.get("case_id"), "status": "completed", "outputs": out})
                except Exception as e:  # noqa: BLE001 — one failed draw must not end the batch
                    results.append({"case_id": case.get("case_id"), "status": "failed",
                                    "error": f"{type(e).__name__}: {e}"[:500]})
            payload: Any = {"results": results, "gtap_cache_hits": n_solves["cache_hits"],
                            "gtap_solves": n_solves["solves"]}
        else:
            payload = run_case(data, solve, coupling, fixed_point, extract_metric, n_solves)
    finally:
        server.close()
    args.out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return 0


def run_case(data: dict[str, Any], solve: Callable[[dict], dict], coupling: Any, fixed_point: Any,
             extract_metric: Callable[..., float | None], n_solves: dict[str, int]) -> dict[str, Any]:
    """One scenario: E0 zero-shock solve, then the GTAP-crop fixed point."""
    shocks = data["shocks"]
    parameters = data.get("gtap_parameter_edits") or None
    started = time.time()
    hits0, solves0 = n_solves["cache_hits"], n_solves["solves"]
    zero = solve(make_request([], 1.0, parameters))
    regions = [str(r) for r in (zero.get("regions") or [])]
    base_apply = shock_instructions(shocks, regions)
    yield_at, baseline_n = fixed_point.emulator_yield()
    fp = run_fixed_point(
        solve, extract_metric, yield_at, coupling.consumption_to_nitrogen,
        base_apply, baseline_n,
        coupling_elasticity=float(data.get("coupling_elasticity", 1.0)),
        parameters=parameters,
        max_iter=int(data.get("max_fixed_point_iter", 12)),
    )
    outputs = assemble_outputs(fp, zero, baseline_n, extract_metric)
    outputs["_execution_mode"] = "julia"
    outputs["_driver"] = {
        "calib_id": os.environ.get("AGRES_CALIB_ID"),
        "gtap_cache_hits": n_solves["cache_hits"] - hits0,
        "gtap_solves": n_solves["solves"] - solves0,
        "wall_seconds": round(time.time() - started, 2),
        "n_shock_instructions": len(base_apply),
        "gtap_parameter_edits": parameters,
        "shocks": shocks,
        "crop_model": "AgResilience APSIM maize emulator (src/tools/get_apsim.py)",
    }
    return outputs


if __name__ == "__main__":
    raise SystemExit(main())
