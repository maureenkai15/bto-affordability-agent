"""HDB loan maths: instalment, tenure and the three limits on the loan size."""
from __future__ import annotations

import math

from . import policy


def monthly_instalment(principal: float, annual_rate: float | None = None, years: int | None = None) -> float:
    """Standard annuity formula: P * r / (1 - (1 + r)^-n)."""
    annual_rate = policy.value("hdb_loan", "interest_rate") if annual_rate is None else annual_rate
    years = policy.value("hdb_loan", "max_tenure_years") if years is None else years
    if principal <= 0:
        return 0.0
    n = years * 12
    r = annual_rate / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def principal_for_instalment(instalment: float, annual_rate: float, years: int) -> float:
    """Inverse of monthly_instalment: the largest loan a given monthly payment can service."""
    n = years * 12
    r = annual_rate / 12
    if r == 0:
        return instalment * n
    return instalment * (1 - (1 + r) ** -n) / r


def loan_tenure(average_applicant_age_at_loan: float) -> int:
    """Shorter of the max tenure and the age limit minus the applicants' average age, in whole years (rounded down)."""
    max_years = policy.value("hdb_loan", "max_tenure_years")
    age_limit = policy.value("hdb_loan", "tenure_age_limit")
    return max(0, min(max_years, math.floor(age_limit - average_applicant_age_at_loan)))


def max_loan(
    flat_price: float,
    grants: float,
    monthly_household_income: float,
    average_applicant_age_at_loan: float,
) -> dict:
    """The HDB loan is the smallest of three limits: LTV, MSR, and what you actually need.

    HDB sizes the MSR limit at the higher of the rate floor and the actual rate; the instalment uses the actual rate.
    """
    rate = policy.value("hdb_loan", "interest_rate")
    assessment_rate = max(rate, policy.value("hdb_loan", "assessment_rate_floor"))
    ltv = policy.value("hdb_loan", "ltv")
    msr = policy.value("hdb_loan", "msr")
    tenure = loan_tenure(average_applicant_age_at_loan)

    by_ltv = flat_price * ltv
    max_instalment = monthly_household_income * msr
    by_msr = principal_for_instalment(max_instalment, assessment_rate, tenure) if tenure > 0 else 0.0
    needed = max(0.0, flat_price - grants)

    limits = {"ltv": by_ltv, "msr": by_msr, "needed": needed}
    binding = min(limits, key=limits.get)
    loan = round(limits[binding], 2)
    instalment = monthly_instalment(loan, rate, tenure) if tenure > 0 else 0.0

    labels = {
        "ltv": f"{ltv:.0%} loan-to-value cap",
        "msr": f"{msr:.0%} mortgage servicing ratio",
        "needed": "price minus grants (you don't need more)",
    }
    return {
        "loan": loan,
        "binding_limit": binding,
        "binding_limit_label": labels[binding],
        "limit_ltv": round(by_ltv, 2),
        "limit_msr": round(by_msr, 2),
        "limit_needed": round(needed, 2),
        "tenure_years": tenure,
        "interest_rate": rate,
        "assessment_rate": assessment_rate,
        "monthly_instalment": round(instalment, 2),
        "msr_max_instalment": round(max_instalment, 2),
        "msr_used_pct": round(instalment / monthly_household_income * 100, 1) if monthly_household_income else None,
    }
