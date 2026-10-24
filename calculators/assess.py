"""Full deterministic assessment: chains every calculator in the right order.

The agent can call the individual tools step by step, or this one for a complete picture.
Scenario tests and the UI breakdown panel both use this, so the numbers are always identical.
"""
from __future__ import annotations

from . import policy
from .cash import cash_gap, months_to_close_gap
from .eligibility import check_eligibility
from .grants import get_ehg_grant
from .loan import max_loan
from .upfront import upfront_costs

EMERGENCY_BUFFER_MONTHS = 6  # assumption: keep 6 months of instalments in cash after buying


def get_project_price(project_id: str, flat_type: str = "4-room", point: str = "low") -> dict:
    projects = policy.node("projects")
    if project_id not in projects:
        return {"error": f"Unknown project '{project_id}'. Known: {', '.join(projects)}"}
    p = projects[project_id]
    prices = p["prices"].get(flat_type.lower())
    if not prices:
        return {"error": f"No {flat_type} price for {p['name']}. Known: {', '.join(p['prices'])}"}
    return {
        "project": p["name"],
        "town": p["town"],
        "exercise": p["exercise"],
        "classification": p["classification"],
        "mop_years": p["mop_years"],
        "flat_type": flat_type,
        "price_low": prices["low"],
        "price_high": prices["high"],
        "price_used": prices[point],
        "status": p["status"],
        "source_url": p["source_url"],
    }


def assess_household(
    household_type: str,
    incomes: list[float],
    ages: list[int],
    cpf_oa_balances: list[float],
    cash_savings: float,
    flat_price: float,
    flat_type: str = "4-room",
    years_until_key_collection: int = 0,
    monthly_savings: float = 0.0,
    all_singapore_citizens: bool = True,
    first_timers: bool = True,
) -> dict:
    income = float(sum(incomes))
    average_age_at_loan = sum(ages) / len(ages) + years_until_key_collection

    elig = check_eligibility(household_type, income, ages, all_singapore_citizens, first_timers)
    ehg = get_ehg_grant(household_type, income, first_timers)
    grants = ehg["grant"]

    if elig["eligible"]:
        loan = max_loan(flat_price, grants, income, average_age_at_loan)
    else:
        loan = {"loan": 0.0, "binding_limit": "ineligible", "binding_limit_label": "not eligible for HDB loan",
                "monthly_instalment": 0.0, "tenure_years": 0, "msr_used_pct": None}

    upfront = upfront_costs(flat_price, flat_type)
    cash_buffer = EMERGENCY_BUFFER_MONTHS * loan["monthly_instalment"]
    cash = cash_gap(
        flat_price=flat_price,
        grants=grants,
        loan=loan["loan"],
        cpf_oa_total=float(sum(cpf_oa_balances)),
        cash_savings=cash_savings,
        upfront_total=upfront["total"],
        cash_buffer_target=cash_buffer,
    )
    if not elig["eligible"]:
        cash["verdict"] = "ineligible"

    return {
        "inputs": {
            "household_type": household_type,
            "monthly_household_income": income,
            "ages": ages,
            "average_age_at_loan": average_age_at_loan,
            "cpf_oa_total": float(sum(cpf_oa_balances)),
            "cash_savings": cash_savings,
            "flat_price": flat_price,
            "flat_type": flat_type,
        },
        "eligibility": elig,
        "grant": ehg,
        "loan": loan,
        "upfront": upfront,
        "cash": cash,
        "months_to_close_gap": months_to_close_gap(cash["gap"], monthly_savings) if cash["gap"] else 0,
        "assumptions": [
            f"Policy values as of {policy.as_of()}.",
            "Average gross monthly household income over the past 12 months equals the incomes given.",
            "No other grants (e.g. Proximity Housing Grant does not apply to BTOs).",
            f"HDB loan at {policy.value('hdb_loan', 'interest_rate'):.1%}, tenure {loan['tenure_years']} years "
            f"(shortest of {policy.value('hdb_loan', 'max_tenure_years')} years and "
            f"{policy.value('hdb_loan', 'tenure_age_limit')} minus the applicants' average age at key collection).",
            f"Loan size under the {policy.value('hdb_loan', 'msr'):.0%} MSR is assessed at the "
            f"{policy.value('hdb_loan', 'assessment_rate_floor'):.1%} interest rate floor, as HDB does.",
            "CPF OA balances are used for the downpayment before cash.",
            f"You should keep {EMERGENCY_BUFFER_MONTHS} months of instalments as emergency cash.",
            "Upfront costs (option fee, stamp duty, legal) are estimates.",
        ],
        "warnings": _warnings(ehg),
        "disclaimer": policy.value("meta", "disclaimer"),
    }


def _warnings(ehg: dict) -> list[str]:
    w: list[str] = []
    if policy.is_stale():
        w.append(f"Policy file is older than {policy.value('meta', 'stale_after_days')} days. Re-check HDB rules.")
    if ehg.get("verified") is False:
        w.append("Singles EHG bands are an estimate (half-scale of the family table). Confirm with HDB.")
    unverified = policy.unverified_items()
    if unverified:
        w.append("Some values are placeholders to confirm: " + ", ".join(unverified))
    return w
