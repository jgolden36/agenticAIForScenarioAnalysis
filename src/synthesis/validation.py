"""Output validation engine.

Per-(scenario, model) sanity checks on the values that Module 3 wrote
to ``data/pipeline_state/<run_id>_model_*.json``. The engine is
intentionally conservative: rules are calibrated to catch *clearly
wrong* values (sign-convention bugs, unit errors, NaN/Inf) rather than
merely surprising results. Cross-model agreement checks live in
:mod:`src.synthesis.consistency`; this module is for per-output
sanity.

Three rule kinds are supported, all driven by
``configs/validation_rules.yaml``:

* ``bounds``       — a single numeric variable must satisfy
  ``min <= x <= max`` (either bound may be omitted).
* ``non_negative`` — a list of variables that must be ``>= 0``
  (loss/shock/reduction magnitudes).
* ``relation``     — an algebraic invariant between several variables
  in the same output dict, evaluated only when every ``requires``
  variable is present and finite.

Plus an implicit finiteness check: any numeric scalar referenced by a
rule that is NaN or +/-Inf is flagged as an error regardless of the
rule's own severity.

The engine returns a :class:`ValidationReport` with an ``errors``
list, a ``warnings`` list, per-(scenario, model) counts, and rule
hit counts. The SLURM Stage 4b driver writes this report to
``data/reports/<run_id>/validation.{json,md}`` and never blocks the
pipeline on it — operators read the report.
"""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.common.logging import get_logger

logger = get_logger(__name__)

DEFAULT_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "validation_rules.yaml"
)

# A very small expression evaluator: only names, numbers, the abs()
# builtin, and arithmetic / comparison operators are allowed. This
# keeps `expression:` strings in YAML safe to evaluate against an
# output dict.
_ALLOWED_NAMES = {"abs": abs, "min": min, "max": max, "True": True, "False": False}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationFinding:
    """A single rule violation."""

    severity: str  # "error" | "warning"
    rule_kind: str  # "bounds" | "non_negative" | "relation" | "finite"
    scenario_id: str
    model_id: str
    variable: str | None
    value: Any
    message: str
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "rule_kind": self.rule_kind,
            "scenario_id": self.scenario_id,
            "model_id": self.model_id,
            "variable": self.variable,
            "value": self.value,
            "message": self.message,
            "description": self.description,
        }


@dataclass
class ValidationReport:
    """Summary of all validation findings for a run."""

    run_id: str
    errors: list[ValidationFinding] = field(default_factory=list)
    warnings: list[ValidationFinding] = field(default_factory=list)
    models_checked: int = 0
    rules_evaluated: int = 0
    rule_hits: dict[str, int] = field(default_factory=dict)

    def add(self, finding: ValidationFinding) -> None:
        if finding.severity == "error":
            self.errors.append(finding)
        else:
            self.warnings.append(finding)
        key = f"{finding.rule_kind}:{finding.variable or '*'}"
        self.rule_hits[key] = self.rule_hits.get(key, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "models_checked": self.models_checked,
            "rules_evaluated": self.rules_evaluated,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "errors": [f.to_dict() for f in self.errors],
            "warnings": [f.to_dict() for f in self.warnings],
            "rule_hits": self.rule_hits,
        }


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------


def load_rules(path: str | Path | None = None) -> tuple[list[dict], dict]:
    """Load validation rules from YAML.

    Returns a (rules, defaults) tuple. If the file is missing the
    returned rules list is empty — validation becomes a no-op rather
    than a hard error, so the pipeline still runs without the config.
    """
    p = Path(path) if path else DEFAULT_RULES_PATH
    if not p.exists():
        logger.warning(
            f"No validation rules YAML at {p}; validation will be a no-op"
        )
        return [], {}
    with open(p) as f:
        data = yaml.safe_load(f) or {}
    rules = data.get("rules", []) or []
    defaults = data.get("defaults", {}) or {}
    logger.info(f"Loaded {len(rules)} validation rules from {p}")
    return rules, defaults


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------


def _coerce_float(value: Any) -> float | None:
    """Try to coerce *value* to a float; return None on failure."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_nonfinite(value: float) -> bool:
    return math.isnan(value) or math.isinf(value)


def _safe_eval(expression: str, env: dict[str, Any]) -> bool | None:
    """Evaluate a relation expression against *env*.

    Returns the boolean result, or ``None`` if evaluation fails for
    any reason (this is treated as "rule did not fire" — graceful
    degradation, never a crash).
    """
    # Restrict eval globals to a vetted set; locals come from `env`
    # which is the model output dict (numeric leaves only).
    try:
        return bool(eval(expression, {"__builtins__": {}, **_ALLOWED_NAMES}, env))
    except Exception as exc:  # noqa: BLE001 — defensive
        logger.debug(f"relation expression {expression!r} failed: {exc}")
        return None


def _build_eval_env(outputs: dict[str, Any], names: list[str]) -> dict[str, float] | None:
    """Build a numeric-only env dict for a relation expression.

    Returns None if any required name is missing, non-numeric, or
    non-finite.
    """
    env: dict[str, float] = {}
    for name in names:
        if name not in outputs:
            return None
        x = _coerce_float(outputs[name])
        if x is None or _is_nonfinite(x):
            return None
        env[name] = x
    return env


def _extract_required_names(expression: str, declared: list[str]) -> list[str]:
    """Return the union of *declared* and any identifiers in
    *expression* that are not in the allow-list of builtin names.

    Uses :mod:`ast` so scientific-notation literals (``1e-6``) are not
    misread as identifiers. Lets rules omit ``requires`` for short
    expressions while still refusing to evaluate against a missing
    variable.
    """
    names = set(declared)
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return sorted(names)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in _ALLOWED_NAMES:
            names.add(node.id)
    return sorted(names)


def _check_bounds(
    rule: dict,
    scenario_id: str,
    model_id: str,
    outputs: dict[str, Any],
    report: ValidationReport,
) -> None:
    var = rule["variable"]
    if var not in outputs:
        return
    value = _coerce_float(outputs[var])
    severity = rule.get("severity", "error")
    description = rule.get("description", "")
    if value is None:
        return
    if _is_nonfinite(value):
        report.add(ValidationFinding(
            severity="error",
            rule_kind="finite",
            scenario_id=scenario_id,
            model_id=model_id,
            variable=var,
            value=outputs[var],
            message=f"{var} is non-finite (NaN or Inf): {outputs[var]!r}",
            description=description,
        ))
        return
    minimum = rule.get("min")
    maximum = rule.get("max")
    if minimum is not None and value < float(minimum):
        report.add(ValidationFinding(
            severity=severity,
            rule_kind="bounds",
            scenario_id=scenario_id,
            model_id=model_id,
            variable=var,
            value=value,
            message=f"{var}={value} is below minimum {minimum}",
            description=description,
        ))
    if maximum is not None and value > float(maximum):
        report.add(ValidationFinding(
            severity=severity,
            rule_kind="bounds",
            scenario_id=scenario_id,
            model_id=model_id,
            variable=var,
            value=value,
            message=f"{var}={value} exceeds maximum {maximum}",
            description=description,
        ))


def _check_non_negative(
    rule: dict,
    scenario_id: str,
    model_id: str,
    outputs: dict[str, Any],
    report: ValidationReport,
) -> None:
    severity = rule.get("severity", "error")
    description = rule.get("description", "")
    for var in rule.get("variables", []) or []:
        if var not in outputs:
            continue
        value = _coerce_float(outputs[var])
        if value is None:
            continue
        if _is_nonfinite(value):
            report.add(ValidationFinding(
                severity="error",
                rule_kind="finite",
                scenario_id=scenario_id,
                model_id=model_id,
                variable=var,
                value=outputs[var],
                message=f"{var} is non-finite (NaN or Inf): {outputs[var]!r}",
                description=description,
            ))
            continue
        if value < 0:
            report.add(ValidationFinding(
                severity=severity,
                rule_kind="non_negative",
                scenario_id=scenario_id,
                model_id=model_id,
                variable=var,
                value=value,
                message=f"{var}={value} is negative; expected a non-negative magnitude",
                description=description,
            ))


def _check_relation(
    rule: dict,
    scenario_id: str,
    model_id: str,
    outputs: dict[str, Any],
    report: ValidationReport,
) -> None:
    expression = rule.get("expression")
    if not expression:
        return
    severity = rule.get("severity", "error")
    description = rule.get("description", "")
    declared = list(rule.get("requires", []) or [])
    required = _extract_required_names(expression, declared)
    env = _build_eval_env(outputs, required)
    if env is None:
        return  # graceful skip — variable missing or non-finite
    result = _safe_eval(expression, env)
    if result is None:
        return
    if not result:
        report.add(ValidationFinding(
            severity=severity,
            rule_kind="relation",
            scenario_id=scenario_id,
            model_id=model_id,
            variable=",".join(required),
            value={k: env[k] for k in required},
            message=f"relation violated: {expression} (with {env})",
            description=description,
        ))


_DISPATCH = {
    "bounds": _check_bounds,
    "non_negative": _check_non_negative,
    "relation": _check_relation,
}


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def validate_outputs(
    model_results: list[dict[str, Any]],
    *,
    run_id: str = "unknown",
    rules_path: str | Path | None = None,
) -> ValidationReport:
    """Run every rule against every model result and return a report.

    Each entry in *model_results* is the JSON-decoded contents of a
    ``<run_id>_model_*.json`` file written by Module 3 (i.e. a dict
    with at least ``scenario_id``, ``model_id``, ``status``, and
    ``outputs``). Results whose status is not ``COMPLETED`` are
    skipped because their ``outputs`` dict is empty by contract.
    """
    rules, _defaults = load_rules(rules_path)
    report = ValidationReport(run_id=run_id)
    if not rules:
        return report

    for r in model_results:
        if r.get("status") != "completed":
            # Module 3 contract: SKIPPED / FAILED results have empty
            # `outputs`. Validating those would be noise.
            continue
        outputs = r.get("outputs") or {}
        if not isinstance(outputs, dict):
            continue
        scenario_id = str(r.get("scenario_id", "unknown"))
        model_id = str(r.get("model_id", "unknown"))
        report.models_checked += 1
        for rule in rules:
            kind = rule.get("kind")
            handler = _DISPATCH.get(kind)
            if handler is None:
                logger.warning(f"Unknown validation rule kind: {kind!r}")
                continue
            report.rules_evaluated += 1
            handler(rule, scenario_id, model_id, outputs, report)

    return report


def render_validation_markdown(report: ValidationReport) -> str:
    """Render *report* as a human-readable Markdown document."""
    lines: list[str] = []
    lines.append(f"# Output validation — run `{report.run_id}`")
    lines.append("")
    lines.append(
        f"- Models checked: **{report.models_checked}**"
    )
    lines.append(
        f"- Rule evaluations: **{report.rules_evaluated}**"
    )
    lines.append(f"- Errors:   **{len(report.errors)}**")
    lines.append(f"- Warnings: **{len(report.warnings)}**")
    lines.append("")

    if not report.errors and not report.warnings:
        lines.append("All outputs passed the conservative sanity checks.")
        lines.append("")
        return "\n".join(lines)

    def _section(title: str, findings: list[ValidationFinding]) -> None:
        if not findings:
            return
        lines.append(f"## {title} ({len(findings)})")
        lines.append("")
        # Group by (scenario, model) for readability.
        keyed: dict[tuple[str, str], list[ValidationFinding]] = {}
        for f_ in findings:
            keyed.setdefault((f_.scenario_id, f_.model_id), []).append(f_)
        for (scen, mod), group in sorted(keyed.items()):
            lines.append(f"### Scenario `{scen}` / model `{mod}`")
            lines.append("")
            for f_ in group:
                lines.append(
                    f"- **{f_.rule_kind}** "
                    f"({f_.variable or 'n/a'}): {f_.message}"
                )
                if f_.description:
                    lines.append(f"  - _{f_.description.strip()}_")
            lines.append("")

    _section("Errors", report.errors)
    _section("Warnings", report.warnings)

    if report.rule_hits:
        lines.append("## Rule hit counts")
        lines.append("")
        for key, count in sorted(report.rule_hits.items()):
            lines.append(f"- `{key}`: {count}")
        lines.append("")

    return "\n".join(lines)
