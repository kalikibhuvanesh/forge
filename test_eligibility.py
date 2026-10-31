"""All rule data here is a SYNTHETIC TEST FIXTURE, not any real scheme's criteria."""
from app.eligibility.engine import ELIGIBLE, INELIGIBLE, INSUFFICIENT, evaluate

SRC = "https://example.gov.in/guideline.pdf"
CRIT = [
    {"field": "family_income_annual", "operator": "<=", "expected_value": 450000,
     "source_reference": SRC, "verified": True},
    {"field": "study_mode", "operator": "==", "expected_value": "regular",
     "source_reference": SRC, "verified": True},
]


def run(profile, criteria=CRIT, rule_year="2026-27", approved=True):
    return evaluate("t", rule_year, criteria, profile, "2026-27", approved)


def test_eligible_when_all_satisfied():
    r = run({"family_income_annual": 300000, "study_mode": "Regular"})
    assert r.overall == ELIGIBLE and all(c.source_reference for c in r.conditions)


def test_missing_information_is_never_satisfied():
    r = run({"study_mode": "regular"})
    assert r.overall == INSUFFICIENT and r.missing_fields == ["family_income_annual"]


def test_blank_string_counts_as_missing():
    assert run({"family_income_annual": "  ", "study_mode": "regular"}).overall == INSUFFICIENT


def test_mandatory_failure_is_ineligible_even_with_other_missing():
    r = run({"family_income_annual": 900000})
    assert r.overall == INELIGIBLE


def test_unverified_criterion_blocks_eligible():
    crit = [dict(CRIT[0]), {**CRIT[1], "verified": False}]
    r = run({"family_income_annual": 1, "study_mode": "regular"}, crit)
    assert r.overall == INSUFFICIENT


def test_unapproved_ruleset_cannot_assess():
    assert run({"family_income_annual": 1, "study_mode": "regular"}, approved=False).overall == INSUFFICIENT


def test_rules_from_other_year_not_applied():
    assert run({"family_income_annual": 1, "study_mode": "regular"}, rule_year="2025-26").overall == INSUFFICIENT


def test_non_numeric_income_is_not_satisfied():
    assert run({"family_income_annual": "lots", "study_mode": "regular"}).overall == INSUFFICIENT


def test_bool_is_not_a_number():
    assert run({"family_income_annual": True, "study_mode": "regular"}).overall == INSUFFICIENT


def test_in_operator():
    crit = [{"field": "category", "operator": "in", "expected_value": ["sc", "st"],
             "source_reference": SRC, "verified": True}]
    assert run({"category": "SC"}, crit).overall == ELIGIBLE
    assert run({"category": "general"}, crit).overall == INELIGIBLE
