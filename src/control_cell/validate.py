"""Menu validation for LLM drafts: accept an item as it is, or reject it with reasons.

The game sends its menus with every request. A menu entry looks like::

    {"label": "Drought",
     "fields": {"team": {"options": ["US", "...", "ROW"]},
                "crop": {"options": ["wheat", "rice", "maize", "soybeans", "ALL"]},
                "a": {"name": "water_deficit_pct", "label": "water deficit pct", "min": 5, "max": 90},
                "b": {"name": "...", "min": 0, "max": 1, "required": false},
                "text": {"name": "pathogen", "required": true, "max_len": 300}}}

Rules, all of them reasons to reject and none of them a reason to repair:

- the move or order type must be in the menu;
- every field the entry declares is required unless it says ``"required": false``;
- a pick-list value must be one of its ``options``;
- a number must lie within ``[min, max]`` and be whole when ``int`` is set;
- text must not exceed ``max_len`` (300 by default);
- a field the entry does not declare must be null.
"""
from __future__ import annotations

from typing import Any

CHOICE_FIELDS: tuple[str, ...] = ("team", "crop", "partner")
NUMBER_FIELDS: tuple[str, ...] = ("a", "b")
ALL_FIELDS: tuple[str, ...] = CHOICE_FIELDS + NUMBER_FIELDS + ("text",)
TEXT_MAX = 300


def _label(spec: dict[str, Any], key: str) -> str:
    return str(spec.get("name") or spec.get("label") or key)


def validate_fields(kind: str, fields: dict[str, Any], menu: dict[str, dict[str, Any]]) -> list[str]:
    """Reasons the item ``kind`` with ``fields`` does not fit ``menu``. Empty means it fits."""
    entry = menu.get(kind)
    if entry is None:
        return [f"{kind!r} is not on the menu (the menu has {', '.join(sorted(menu))})"]
    declared = dict(entry.get("fields") or {})
    reasons: list[str] = []
    for key in ALL_FIELDS:
        value = fields.get(key)
        spec = declared.get(key)
        if spec is None:
            if value not in (None, ""):
                reasons.append(f"{kind}: field {key!r} is not part of this move but carries {value!r}")
            continue
        spec = dict(spec) if isinstance(spec, dict) else {}
        required = spec.get("required", True) is not False
        name = _label(spec, key)
        if value is None or value == "":
            if required:
                reasons.append(f"{kind}: {name} ({key}) is required")
            continue
        if key in CHOICE_FIELDS:
            options = spec.get("options")
            if options is not None and value not in list(options):
                reasons.append(f"{kind}: {name} = {value!r} is not one of {list(options)}")
        elif key in NUMBER_FIELDS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                reasons.append(f"{kind}: {name} = {value!r} is not a number")
                continue
            lo, hi = spec.get("min"), spec.get("max")
            if lo is not None and float(value) < float(lo):
                reasons.append(f"{kind}: {name} = {value:g} is below min {lo}")
            if hi is not None and float(value) > float(hi):
                reasons.append(f"{kind}: {name} = {value:g} is above max {hi}")
            if spec.get("int") and float(value) != int(float(value)):
                reasons.append(f"{kind}: {name} = {value:g} must be a whole number")
        else:
            if not isinstance(value, str):
                reasons.append(f"{kind}: {name} must be text")
            elif len(value) > int(spec.get("max_len", TEXT_MAX)):
                reasons.append(f"{kind}: {name} is longer than {int(spec.get('max_len', TEXT_MAX))} characters")
    return reasons


def fields_for(kind_fields: tuple[str, ...], fields: dict[str, Any]) -> dict[str, Any]:
    """The wire form of an item's fields: exactly ``kind_fields``, null when absent."""
    return {k: fields.get(k) for k in kind_fields}
