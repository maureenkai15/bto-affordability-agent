"""What if we apply later? Project CPF OA, cash and income forward a year at a time and re-run the assessment."""
from __future__ import annotations

from . import policy
from .assess import assess_household


def cpf_oa_monthly(monthly_wage: float, age: float) -> float:
    """Monthly CPF contribution allocated to the Ordinary Account, on Ordinary Wages up to the ceiling."""
    if monthly_wage <= policy.value("cpf", "min_wage_full_rate"):
        return 0.0
    wage = min(monthly_wage, policy.value("cpf", "ordinary_wage_ceiling"))
    for band in policy.node("cpf", "contribution_and_allocation")["bands"]:
        if band["max_age"] is None or age <= band["max_age"]:
            return round(wage * band["total_rate"] * band["oa_ratio"], 2)
    raise ValueError("CPF bands do not cover this age - check policy_2026.yaml")


def project_household(
    request: dict,
    years: int,
    income_growth: float = 0.0,
    price_growth: float = 0.0,
) -> list[dict]:
    """Re-run assess_household for applying now and in each of the next `years` years.

    Each year: incomes grow by income_growth, OA earns interest on the opening balance and gets 12 months of
    contributions (at the opening year's age and wage), cash grows by 12 months of savings, the flat price
    grows by price_growth. Simplified: yearly steps, no bonuses, no extra OA interest.
    """
    oa_rate = policy.value("cpf", "oa_interest_rate")
    incomes = [float(i) for i in request["incomes"]]
    ages = [float(a) for a in request["ages"]]
    oa = float(sum(request["cpf_oa_balances"]))
    cash = float(request["cash_savings"])
    price = float(request["flat_price"])
    out = []
    for year in range(years + 1):
        r = assess_household(**{**request, "incomes": [round(i, 2) for i in incomes],
                                 "ages": [int(a) for a in ages], "cpf_oa_balances": [round(oa, 2)],
                                 "cash_savings": round(cash, 2), "flat_price": round(price, 2)})
        out.append({
            "years_from_now": year,
            "monthly_household_income": r["inputs"]["monthly_household_income"],
            "cpf_oa_total": r["inputs"]["cpf_oa_total"],
            "cash_savings": r["inputs"]["cash_savings"],
            "flat_price": r["inputs"]["flat_price"],
            "eligible": r["eligibility"]["eligible"],
            "grant": r["grant"]["grant"],
            "loan": r["loan"]["loan"],
            "verdict": r["cash"]["verdict"],
            "gap": r["cash"]["gap"],
            "cash_left_after": r["cash"]["cash_left_after"],
        })
        contributions = sum(cpf_oa_monthly(i, a) for i, a in zip(incomes, ages)) * 12
        oa = oa * (1 + oa_rate) + contributions
        cash += request.get("monthly_savings", 0.0) * 12
        incomes = [i * (1 + income_growth) for i in incomes]
        ages = [a + 1 for a in ages]
        price *= 1 + price_growth
    return out
