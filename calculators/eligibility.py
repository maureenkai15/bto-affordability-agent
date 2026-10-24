"""Can this household buy a BTO and take an HDB loan at all?"""
from __future__ import annotations

from typing import Literal

from . import policy

HouseholdType = Literal["family", "single"]


def check_eligibility(
    household_type: HouseholdType,
    monthly_household_income: float,
    applicant_ages: list[int],
    all_singapore_citizens: bool = True,
    first_timers: bool = True,
) -> dict:
    """Return eligibility for a new BTO flat + HDB loan, with plain-English reasons."""
    reasons: list[str] = []
    notes: list[str] = []
    eligible = True

    if household_type == "single":
        ceiling = policy.value("income_ceilings", "single_35_plus")
        min_age = policy.value("single_min_age")
        if max(applicant_ages) < min_age:
            eligible = False
            reasons.append(f"Singles must be at least {min_age} to buy a BTO.")
        notes.append("Singles have flat-type and location limits. Confirm which flats you can apply for.")
    else:
        ceiling = policy.value("income_ceilings", "family")

    if monthly_household_income > ceiling:
        eligible = False
        reasons.append(
            f"Household income ${monthly_household_income:,.0f}/month is above the ${ceiling:,.0f} ceiling "
            "for new flats and HDB loans."
        )
    else:
        notes.append(f"Income is within the ${ceiling:,.0f}/month ceiling.")

    if not all_singapore_citizens:
        notes.append("Mixed citizenship (e.g. citizen + PR) changes grant amounts and prices. Confirm via HFE letter.")
    if not first_timers:
        notes.append("Second-timers get different grants and priority. This tool assumes first-timers.")

    return {
        "eligible": eligible,
        "income_ceiling": ceiling,
        "reasons": reasons,
        "notes": notes,
        "policy_as_of": policy.as_of(),
    }
