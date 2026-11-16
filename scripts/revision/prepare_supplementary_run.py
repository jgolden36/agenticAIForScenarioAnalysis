"""Seed a supplementary run with a subset of an earlier run's saved parameters.

The supplementary "full models" runs reuse the parameters that the LLM
extracted in run 20260504_222710 (no new LLM call) and execute only:

* the target models (default: opencge, energy_flux_lng_profits, simrlfab,
  mam), and
* every upstream model their forwarding rules read from, followed
  transitively through ``configs/upstream_forwarding_mapping.yaml``
  (e.g. opencge <- energy_flux_lng_profits <- lngst),

so the forwarded inputs are recomputed in the new run instead of being
borrowed from another run's outputs.

The script copies ``<source>_params_*.json`` records for those models to
``<run_id>_params_<n>.json`` (renumbered, content unchanged apart from a
``supplementary_of`` field), copies ``<source>_scenarios.json``, and
writes ``<run_id>_supplementary_manifest.json`` recording the source run,
the model closure, each copied file's SHA-256 and the (scenario, model)
pairs that had no usable source record. It never writes to the source
run's files.

Usage::

    python scripts/revision/prepare_supplementary_run.py \
        --source-run-id 20260504_222710 --run-id supp_full_20260504_222710
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipeline.upstream_forwarding import load_mapping  # noqa: E402

DEFAULT_TARGETS = ("opencge", "energy_flux_lng_profits", "simrlfab", "mam")
# Fallback sources in the closure that cannot run on the cluster yet
# (no Octave/Dynare; SahysMod needs a Windows binary). They only matter
# when a primary source fails, so leaving them out changes no forwarded
# value; it keeps known failures out of the supplementary ledger.
DEFAULT_EXCLUDE = ("bornstein_krusell_rebelo", "sahysmod")


def model_closure(targets: list[str] | tuple[str, ...], mapping=None) -> list[str]:
    """Targets plus every model their forwarding rules read from, transitively."""
    mapping = mapping or load_mapping()
    seen: set[str] = set()
    stack = list(targets)
    while stack:
        m = stack.pop()
        if m in seen:
            continue
        seen.add(m)
        for rule in mapping.by_model.get(m, []):
            for src in rule.sources:
                if src.source_model not in seen:
                    stack.append(src.source_model)
    return sorted(seen)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source_run_id: str, run_id: str, source_state_dir: Path, state_dir: Path,
            targets: list[str], overwrite: bool = False,
            exclude: list[str] | tuple[str, ...] = DEFAULT_EXCLUDE) -> dict:
    if source_run_id == run_id:
        raise ValueError("run_id must differ from source_run_id")
    state_dir.mkdir(parents=True, exist_ok=True)
    existing = glob.glob(str(state_dir / f"{run_id}_params_*.json"))
    if existing and not overwrite:
        raise FileExistsError(f"{len(existing)} params file(s) for {run_id} already exist; pass --overwrite")
    for p in existing:
        Path(p).unlink()

    models = [m for m in model_closure(targets) if m not in set(exclude) or m in targets]
    copied: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()
    scenarios: set[str] = set()
    n = 0
    for pf in sorted(Path(p) for p in glob.glob(str(source_state_dir / f"{source_run_id}_params_*.json"))):
        rec = json.loads(pf.read_text(encoding="utf-8"))
        scenarios.add(rec.get("scenario_id"))
        if rec.get("model_id") not in models:
            continue
        status = str(rec.get("status") or "completed").lower()
        usable = status != "failed" and isinstance(rec.get("parameters"), list)
        if not usable:
            continue
        rec["supplementary_of"] = {"run_id": source_run_id, "file": pf.name, "sha256": _sha256(pf)}
        dest = state_dir / f"{run_id}_params_{n}.json"
        dest.write_text(json.dumps(rec, indent=2, default=str), encoding="utf-8")
        copied.append({"source": pf.name, "dest": dest.name, "scenario_id": rec.get("scenario_id"),
                       "model_id": rec.get("model_id")})
        seen_pairs.add((rec.get("scenario_id"), rec.get("model_id")))
        n += 1

    scen_src = source_state_dir / f"{source_run_id}_scenarios.json"
    if scen_src.exists():
        (state_dir / f"{run_id}_scenarios.json").write_bytes(scen_src.read_bytes())

    scenarios.discard(None)
    missing = sorted(
        f"{s}/{m}" for s in scenarios for m in models if (s, m) not in seen_pairs
    )
    manifest = {
        "run_id": run_id,
        "source_run_id": source_run_id,
        "source_state_dir": str(source_state_dir),
        "targets": list(targets),
        "model_closure": models,
        "excluded_fallback_sources": sorted(set(exclude) - set(targets)),
        "n_params_copied": len(copied),
        "copied": copied,
        "missing_or_failed_in_source": missing,
        "scenarios_file_copied": scen_src.exists(),
    }
    (state_dir / f"{run_id}_supplementary_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source-run-id", default="20260504_222710")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--source-state-dir", default="data/pipeline_state")
    ap.add_argument("--state-dir", default="data/pipeline_state")
    ap.add_argument("--targets", default=",".join(DEFAULT_TARGETS))
    ap.add_argument("--exclude", default=",".join(DEFAULT_EXCLUDE),
                    help="Fallback sources to leave out (comma list; '' to keep all)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)

    m = prepare(args.source_run_id, args.run_id, Path(args.source_state_dir), Path(args.state_dir),
                [t.strip() for t in args.targets.split(",") if t.strip()], overwrite=args.overwrite,
                exclude=[t.strip() for t in args.exclude.split(",") if t.strip()])
    print(f"model closure ({len(m['model_closure'])}): {', '.join(m['model_closure'])}")
    print(f"copied {m['n_params_copied']} parameter record(s) to {args.state_dir}/{args.run_id}_params_*.json")
    if m["missing_or_failed_in_source"]:
        print(f"no usable source record for {len(m['missing_or_failed_in_source'])} pair(s): "
              + ", ".join(m["missing_or_failed_in_source"]))
    return 0 if m["n_params_copied"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
