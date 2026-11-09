"""Game state -> adapter parameters, driven by ``configs/game/game_state_to_parameters.yaml``.

The mapping file states, for each adapter, every parameter its analytical-MVP path needs as
either a literal or an ``{expr: ...}`` arithmetic expression over the round's world variables,
the frozen baseline and a block of derived quantities. :func:`evaluate` is a deliberately small
evaluator: it accepts arithmetic, comparisons, boolean logic, the ternary, dotted and indexed
lookups, list literals and the functions ``min max abs round clamp``. Anything else raises, so
a rule can be read and checked from the YAML alone.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .baseline import baseline_values, default_mapping_path


class MappingError(ValueError):
    """A rule could not be evaluated."""


# --- the expression evaluator -----------------------------------------------------------------


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


_FUNCS = {"min": min, "max": max, "abs": abs, "round": round, "clamp": _clamp}

_BIN = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a ** b,
}
_CMP = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
}


class _Namespace(dict):
    """Attribute access over a dict so ``world.x`` works in expressions."""

    def __getattr__(self, name):
        try:
            v = self[name]
        except KeyError as e:
            raise MappingError(f"unknown name {name!r}") from e
        return _wrap(v)


def _wrap(v):
    if isinstance(v, dict) and not isinstance(v, _Namespace):
        return _Namespace(v)
    return v


def _eval(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, ctx)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool, str)) or node.value is None:
            return node.value
        raise MappingError(f"unsupported constant {node.value!r}")
    if isinstance(node, ast.Name):
        if node.id in ctx:
            return _wrap(ctx[node.id])
        if node.id in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[node.id]
        raise MappingError(f"unknown name {node.id!r}")
    if isinstance(node, ast.Attribute):
        base = _eval(node.value, ctx)
        if isinstance(base, dict):
            if node.attr not in base:
                raise MappingError(f"unknown field {node.attr!r}")
            return _wrap(base[node.attr])
        raise MappingError(f"cannot read {node.attr!r} from {type(base).__name__}")
    if isinstance(node, ast.Subscript):
        base = _eval(node.value, ctx)
        idx = _eval(node.slice, ctx)
        try:
            if isinstance(base, list):
                return base[int(idx)]
            return _wrap(base[idx])
        except (KeyError, IndexError, TypeError, ValueError) as e:
            raise MappingError(f"bad index {idx!r}") from e
    if isinstance(node, ast.List):
        return [_eval(e, ctx) for e in node.elts]
    if isinstance(node, ast.UnaryOp):
        v = _eval(node.operand, ctx)
        if isinstance(node.op, ast.USub):
            return -v
        if isinstance(node.op, ast.UAdd):
            return +v
        if isinstance(node.op, ast.Not):
            return not v
        raise MappingError("unsupported unary operator")
    if isinstance(node, ast.BinOp):
        fn = _BIN.get(type(node.op))
        if fn is None:
            raise MappingError("unsupported operator")
        return fn(_eval(node.left, ctx), _eval(node.right, ctx))
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, ctx) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ctx)
        for op, comp in zip(node.ops, node.comparators):
            fn = _CMP.get(type(op))
            if fn is None:
                raise MappingError("unsupported comparison")
            right = _eval(comp, ctx)
            if not fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.IfExp):
        return _eval(node.body, ctx) if _eval(node.test, ctx) else _eval(node.orelse, ctx)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise MappingError("only min, max, abs, round and clamp may be called")
        if node.keywords:
            raise MappingError("keyword arguments are not allowed")
        return _FUNCS[node.func.id](*[_eval(a, ctx) for a in node.args])
    raise MappingError(f"unsupported syntax {type(node).__name__}")


def evaluate(expr: str, ctx: dict[str, Any]) -> Any:
    """Evaluate one rule expression against ``ctx`` (``world``, ``baseline``, ``derived``)."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise MappingError(f"cannot parse {expr!r}: {e}") from e
    value = _eval(tree, ctx)
    if isinstance(value, _Namespace):
        return dict(value)
    return value


# --- the mapping file -------------------------------------------------------------------------


@dataclass
class ParameterMapping:
    version: int
    derived: dict[str, Any]
    models: dict[str, dict[str, Any]]
    forwarding_extra: dict[str, Any]
    outputs: dict[str, dict[str, Any]]
    forwarding_disable: list[str] = field(default_factory=list)
    path: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@lru_cache(maxsize=4)
def _load(path: str) -> ParameterMapping:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return ParameterMapping(
        version=int(raw.get("version", 1)),
        derived=dict(raw.get("derived") or {}),
        models=dict(raw.get("models") or {}),
        forwarding_extra=dict(raw.get("forwarding_extra") or {}),
        outputs=dict(raw.get("outputs") or {}),
        forwarding_disable=[str(x) for x in (raw.get("forwarding_disable") or [])],
        path=path,
        raw=raw,
    )


def load_mapping(path: Path | str | None = None) -> ParameterMapping:
    return _load(str(path or default_mapping_path()))


def clear_cache() -> None:
    _load.cache_clear()


def _resolve(rule: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(rule, dict) and set(rule) == {"expr"}:
        return evaluate(str(rule["expr"]), ctx)
    return rule


def build_context(world: dict[str, Any], baseline: dict[str, Any] | None,
                  mapping: ParameterMapping) -> dict[str, Any]:
    """``{world, baseline, derived}`` with the derived block evaluated in file order."""
    ctx: dict[str, Any] = {
        "world": dict(world),
        "baseline": baseline if baseline is not None else baseline_values(),
        "derived": {},
    }
    for name, rule in mapping.derived.items():
        try:
            ctx["derived"][name] = _resolve(rule, ctx)
        except MappingError as e:
            raise MappingError(f"derived.{name}: {e}") from e
    return ctx


def parameters_for(model_id: str, ctx: dict[str, Any], mapping: ParameterMapping) -> dict[str, Any]:
    """The adapter parameter dict for ``model_id`` under ``ctx``."""
    block = mapping.models.get(model_id)
    if block is None:
        raise MappingError(f"no parameter block for {model_id!r}")
    params: dict[str, Any] = {}
    for name, rule in block.items():
        try:
            params[name] = _resolve(rule, ctx)
        except MappingError as e:
            raise MappingError(f"{model_id}.{name}: {e}") from e
    return params


def all_parameters(ctx: dict[str, Any], mapping: ParameterMapping) -> dict[str, dict[str, Any]]:
    return {mid: parameters_for(mid, ctx, mapping) for mid in mapping.models}
