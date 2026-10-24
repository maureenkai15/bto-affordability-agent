"""Loan maths for HDB and bank loans: instalment, tenure, LTV/MSR limits and total interest."""
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


def bank_loan_terms(tenure_years: int, income_weighted_age_at_loan: float) -> dict:
    """MAS rules for a bank loan on an HDB flat: 75% LTV and 5% minimum cash, or 55% and 10% if the tenure is long
    or the loan runs past the age limit (income-weighted average age of the borrowers)."""
    full = (tenure_years <= policy.value("bank_loan", "ltv_tenure_threshold_years")
            and income_weighted_age_at_loan + tenure_years <= policy.value("bank_loan", "age_limit"))
    cash = policy.node("bank_loan", "min_cash_downpayment")
    return {
        "ltv": policy.value("bank_loan", "ltv" if full else "ltv_reduced"),
        "min_cash_pct": cash["at_full_ltv" if full else "at_reduced_ltv"],
        "reduced": not full,
    }


def default_bank_tenure(income_weighted_age_at_loan: float) -> int:
    """Longest bank tenure that keeps the full LTV."""
    return max(0, min(policy.value("bank_loan", "ltv_tenure_threshold_years"),
                      math.floor(policy.value("bank_loan", "age_limit") - income_weighted_age_at_loan)))


def max_loan(
    flat_price: float,
    grants: float,
    monthly_household_income: float,
    average_applicant_age_at_loan: float,
    lender: str = "hdb",
    bank_rate: float | None = None,
    income_weighted_age_at_loan: float | None = None,
    tenure_years: int | None = None,
    desired_loan: float | None = None,
) -> dict:
    """The loan is the smallest of: the LTV cap, the 30% MSR, price minus grants, and what you choose to borrow.

    HDB sizes the MSR limit at its rate floor and banks at the MAS floor; the instalment uses the actual rate.
    lender: "hdb" or "bank". tenure_years: a shorter tenure than the maximum, if wanted.
    """
    msr = policy.value("hdb_loan", "msr")
    if lender == "bank":
        rate = policy.value("bank_loan", "indicative_rate") if bank_rate is None else bank_rate
        assessment_rate = max(rate, policy.value("bank_loan", "assessment_rate_floor"))
        age = average_applicant_age_at_loan if income_weighted_age_at_loan is None else income_weighted_age_at_loan
        max_tenure = policy.value("bank_loan", "max_tenure_years")
        tenure = default_bank_tenure(age) if tenure_years is None else max(0, min(tenure_years, max_tenure))
        terms = bank_loan_terms(tenure, age)
        ltv, min_cash_pct = terms["ltv"], terms["min_cash_pct"]
    else:
        rate = policy.value("hdb_loan", "interest_rate")
        assessment_rate = max(rate, policy.value("hdb_loan", "assessment_rate_floor"))
        max_tenure = loan_tenure(average_applicant_age_at_loan)
        tenure = max_tenure if tenure_years is None else max(0, min(tenure_years, max_tenure))
        ltv, min_cash_pct = policy.value("hdb_loan", "ltv"), 0.0

    by_ltv = flat_price * ltv
    max_instalment = monthly_household_income * msr
    by_msr = principal_for_instalment(max_instalment, assessment_rate, tenure) if tenure > 0 else 0.0
    needed = max(0.0, flat_price - grants)

    limits = {"ltv": by_ltv, "msr": by_msr, "needed": needed}
    if desired_loan is not None:
        limits["chosen"] = max(0.0, desired_loan)
    binding = min(limits, key=limits.get)
    loan = round(limits[binding], 2)
    instalment = monthly_instalment(loan, rate, tenure) if tenure > 0 else 0.0

    labels = {
        "ltv": f"{ltv:.0%} loan-to-value cap",
        "msr": f"{msr:.0%} mortgage servicing ratio",
        "needed": "price minus grants (you don't need more)",
        "chosen": "the amount you chose to borrow",
    }
    return {
        "lender": lender,
        "loan": loan,
        "max_loan": round(min(v for k, v in limits.items() if k != "chosen"), 2),
        "binding_limit": binding,
        "binding_limit_label": labels[binding],
        "limit_ltv": round(by_ltv, 2),
        "limit_msr": round(by_msr, 2),
        "limit_needed": round(needed, 2),
        "ltv": ltv,
        "min_cash_pct": min_cash_pct,
        "tenure_years": tenure,
        "max_tenure_years": max_tenure,
        "interest_rate": rate,
        "assessment_rate": assessment_rate,
        "monthly_instalment": round(instalment, 2),
        "total_interest": round(instalment * tenure * 12 - loan, 2) if tenure > 0 else 0.0,
        "msr_max_instalment": round(max_instalment, 2),
        "msr_used_pct": round(instalment / monthly_household_income * 100, 1) if monthly_household_income else None,
    }
