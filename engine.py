"""Deterministic eligibility engine. No LLM is involved in any decision here.

Rules:
- Only criteria with verified=True and a source_reference are evaluated.
- Missing or unparseable student data is never treated as satisfying a condition.
- Overall: any failed mandatory verified criterion -> INELIGIBLE; else any missing / unverified /
  year-mismatch -> INSUFFICIENT_INFORMATION; else ELIGIBLE.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

ELIGIBLE = "ELIGIBLE"
INELIGIBLE = "INELIGIBLE"
INSUFFICIENT = "INSUFFICIENT_INFORMATION"

SATISFIED = "SATISFIED"
FAILED = "FAILED"
MISSING = "MISSING_INFORMATION"
NOT_EVALUATED = "NOT_EVALUATED_UNVERIFIED_RULE"

NUMERIC_OPS = {"<=", ">=", "<", ">"}
ALL_OPS = NUMERIC_OPS | {"==", "!=", "in", "not_in"}


@dataclass
class ConditionResult:
    field: str
    operator: str
    expected_value: Any
    actual_value: Any
    status: str
    explanation: str
    source_reference: str | None
    mandatory: bool = True


@dataclass
class EligibilityResult:
    scheme_id: str
    academic_year: str
    overall: str
    conditions: list[ConditionResult] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    summary: str = ""


def _norm(v: Any) -> Any:
    if isinstance(v, str):
        return v.strip().lower()
    return v


def _is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _to_decimal(v: Any) -> Decimal | None:
    if isinstance(v, bool):
        return None
    try:
        return Decimal(str(v).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _compare(op: str, actual: Any, expected: Any) -> tuple[bool | None, str]:
    """Returns (result, note). result None means the value could not be compared."""
    if op in NUMERIC_OPS:
        a, e = _to_decimal(actual), _to_decimal(expected)
        if a is None or e is None:
            return None, "value is not a number"
        return {"<=": a <= e, ">=": a >= e, "<": a < e, ">": a > e}[op], ""
    if op == "==":
        return _norm(actual) == _norm(expected), ""
    if op == "!=":
        return _norm(actual) != _norm(expected), ""
    if op in ("in", "not_in"):
        if not isinstance(expected, (list, tuple, set)):
            return None, "rule expected_value must be a list"
        hit = _norm(actual) in {_norm(x) for x in expected}
        return (hit if op == "in" else not hit), ""
    return None, f"unsupported operator {op}"


def evaluate(
    scheme_id: str,
    rule_academic_year: str,
    criteria: list[dict],
    profile: dict,
    target_academic_year: str,
    rule_set_approved: bool,
) -> EligibilityResult:
    res = EligibilityResult(scheme_id=scheme_id, academic_year=target_academic_year, overall=INSUFFICIENT)

    if not rule_set_approved:
        res.summary = "No approved, source-verified rules exist for this scheme yet, so eligibility cannot be assessed."
        return res
    if rule_academic_year != target_academic_year:
        res.summary = (
            f"Approved rules are for {rule_academic_year}, not {target_academic_year}. "
            "Rules from another academic year are not applied."
        )
        return res

    any_failed = any_missing = any_unverified = False
    for c in criteria:
        f, op, exp = c.get("field"), c.get("operator"), c.get("expected_value")
        src, mandatory = c.get("source_reference"), c.get("mandatory", True)
        base = dict(field=f, operator=op, expected_value=exp, source_reference=src, mandatory=mandatory)

        if not c.get("verified") or not src or op not in ALL_OPS:
            any_unverified = True
            res.conditions.append(ConditionResult(**base, actual_value=None, status=NOT_EVALUATED,
                explanation="This condition has no verified official source, so it was not evaluated."))
            continue

        actual = profile.get(f)
        if _is_blank(actual):
            any_missing = True
            res.missing_fields.append(f)
            res.conditions.append(ConditionResult(**base, actual_value=None, status=MISSING,
                explanation=f"'{f}' is needed for this condition and has not been provided."))
            continue

        ok, note = _compare(op, actual, exp)
        if ok is None:
            any_missing = True
            res.missing_fields.append(f)
            res.conditions.append(ConditionResult(**base, actual_value=actual, status=MISSING,
                explanation=f"Could not evaluate '{f}': {note}. Please correct the value."))
        elif ok:
            res.conditions.append(ConditionResult(**base, actual_value=actual, status=SATISFIED,
                explanation=f"{f} = {actual} satisfies the rule ({op} {exp})."))
        else:
            if mandatory:
                any_failed = True
            res.conditions.append(ConditionResult(**base, actual_value=actual, status=FAILED,
                explanation=f"{f} = {actual} does not satisfy the rule ({op} {exp})."))

    res.missing_fields = sorted(set(res.missing_fields))
    if any_failed:
        res.overall, res.summary = INELIGIBLE, "At least one mandatory verified condition is not met."
    elif any_missing or any_unverified:
        res.overall = INSUFFICIENT
        res.summary = "Some conditions could not be evaluated because information or verified rules are missing."
    elif not criteria:
        res.overall, res.summary = INSUFFICIENT, "The approved rule set contains no criteria."
    else:
        res.overall, res.summary = ELIGIBLE, "All verified conditions are satisfied. Read the official guidelines before applying."
    return res
