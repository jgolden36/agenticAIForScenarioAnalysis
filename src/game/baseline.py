"""The frozen Hormuz baseline (``configs/game/hormuz_2026_baseline.yaml``).

Every leaf in the YAML is a record ``{value, unit, source, status[, note]}``. :func:`collapse`
turns the tree into plain values for use in expressions and in the game, while
:func:`load_baseline` keeps the records so the provenance of each number stays attached.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

RECORD_KEYS = {"value", "unit", "source", "status"}


def default_baseline_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "game" / "hormuz_2026_baseline.yaml"


def default_mapping_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configs" / "game" / "game_state_to_parameters.yaml"


def is_record(node: Any) -> bool:
    return isinstance(node, dict) and "value" in node and "status" in node


def collapse(node: Any) -> Any:
    """Replace every ``{value, unit, source, status}`` record with its value, recursively."""
    if is_record(node):
        return collapse(node["value"])
    if isinstance(node, dict):
        return {k: collapse(v) for k, v in node.items()}
    if isinstance(node, list):
        return [collapse(v) for v in node]
    return node


def records(node: Any, prefix: str = "") -> list[dict[str, Any]]:
    """Flatten the tree into one row per sourced value, for audit tables."""
    out: list[dict[str, Any]] = []
    if is_record(node):
        row = {"path": prefix}
        row.update({k: node.get(k) for k in ("value", "unit", "source", "status", "note")})
        return [row]
    if isinstance(node, dict):
        for k, v in node.items():
            out.extend(records(v, f"{prefix}.{k}" if prefix else str(k)))
    return out


@lru_cache(maxsize=4)
def _load(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if "as_of" not in data or "teams" not in data:
        raise ValueError(f"{path} is not a game baseline (needs as_of and teams)")
    return data


def load_baseline(path: Path | str | None = None) -> dict[str, Any]:
    """The raw baseline tree with its provenance records intact."""
    return _load(str(path or default_baseline_path()))


def baseline_values(path: Path | str | None = None) -> dict[str, Any]:
    """The baseline tree with every record collapsed to its value."""
    return collapse(load_baseline(path))


def team_regions(path: Path | str | None = None) -> dict[str, str]:
    teams = load_baseline(path).get("teams") or {}
    return {seat: str(spec.get("region", "ROW")) for seat, spec in teams.items()}


def clear_cache() -> None:
    _load.cache_clear()
