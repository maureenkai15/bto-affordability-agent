"""Full deterministic assessment: chains every calculator in the right order.

The agent can call the individual tools step by step, or this one for a complete picture.
Scenario tests and the UI breakdown panel both use this, so the numbers are always identical.
"""
from __future__ import annotations

from . import policy
from .cash import cash_gap, months_to_close_gap, payment_stages
from .eligibility import check_eligibility
from .grants import get_ehg_grant
from .loan import max_loan
from .upfront import upfront_costs

EMERGENCY_BUFFER_MONTHS = 6  # assumption: keep 6 months of instalments in cash after buying


def list_projects() -> list[dict]:
    """Every known BTO project, launched or upcoming, with the flat types it offers."""
    out = []
    for pid, p in policy.node("projects").items():
        out.append({
            "project_id": pid,
            "name": p["name"],
            "town": p["town"],
            "region": p["region"],
            "classification": p["classification"],
            "exercise": p["exercise"],
            "status": p["status"],
            "units": p["units"],
            "waiting_time_months": p.get("waiting_time_months"),
            "flat_types": list(p["prices"]) if p["status"] == "launched" else p["flat_types"],
            "location": p["location"],
        })
    return out


def get_project_price(project_id: str, flat_type: str = "4-room", point: str = "low") -> dict:
    """Indicative price before grants. Upcoming projects use a published estimate if one exists, otherwise the
    prices of a named launched comparable, clearly labelled as a reference."""
    projects = policy.node("projects")
    if project_id not in projects:
        return {"error": f"Unknown project '{project_id}'. Known: {', '.join(projects)}"}
    p = projects[project_id]
    flat_type = flat_type.lower()
    offered = list(p["prices"]) if p["status"] == "launched" else p["flat_types"]
    if flat_type not in offered:
        return {"error": f"{p['name']} has no {flat_type} flats. Offered: {', '.join(offered)}"}

    if p["status"] == "launched":
        prices, basis, source = p["prices"][flat_type], f"HDB launch price range ({p['exercise']})", p["source_url"]
    elif flat_type in p.get("estimates", {}):
        prices, basis, source = p["estimates"][flat_type], "third-party estimate before launch", p["estimate_source_url"]
    else:
        comp = projects[p["comparable"]]
        prices = comp["prices"][flat_type]
        basis = (f"not released yet; showing {comp['name']} ({comp['exercise']}, {comp['classification']}) "
                 f"as a reference")
        source = comp["source_url"]
    return {
        "project": p["name"],
        "town": p["town"],
        "exercise": p["exercise"],
        "classification": p["classification"],
        "status": p["status"],
        "flat_type": flat_type,
        "price_low": prices["low"],
        "price_high": prices["high"],
        "price_used": prices[point],
        "price_basis": basis,
        "source_url": source,
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
    lender: str = "hdb",
    bank_rate: float | None = None,
    tenure_years: int | None = None,
    desired_loan: float | None = None,
) -> dict:
    request = {k: v for k, v in locals().items()}  # the exact inputs, so callers can re-run a what-if
    income = float(sum(incomes))
    average_age_at_loan = sum(ages) / len(ages) + years_until_key_collection
    # MAS uses the income-weighted average age for joint bank borrowers
    income_weighted_age_at_loan = (
        sum(a * i for a, i in zip(ages, incomes)) / income if income else sum(ages) / len(ages)
    ) + years_until_key_collection

    elig = check_eligibility(household_type, income, ages, all_singapore_citizens, first_timers)
    ehg = get_ehg_grant(household_type, income, first_timers)
    grants = ehg["grant"]

    if elig["eligible"]:
        loan = max_loan(flat_price, grants, income, average_age_at_loan, lender=lender, bank_rate=bank_rate,
                        income_weighted_age_at_loan=income_weighted_age_at_loan, tenure_years=tenure_years,
                        desired_loan=desired_loan)
    else:
        loan = {"lender": lender, "loan": 0.0, "max_loan": 0.0, "binding_limit": "ineligible",
                "binding_limit_label": "not eligible to buy a new flat", "ltv": 0.0, "min_cash_pct": 0.0,
                "monthly_instalment": 0.0, "total_interest": 0.0, "tenure_years": 0, "max_tenure_years": 0,
                "interest_rate": 0.0, "assessment_rate": 0.0, "msr_used_pct": None}

    upfront = upfront_costs(flat_price, flat_type, loan["loan"])
    cash_buffer = EMERGENCY_BUFFER_MONTHS * loan["monthly_instalment"]
    cash = cash_gap(
        flat_price=flat_price,
        grants=grants,
        loan=loan["loan"],
        cpf_oa_total=float(sum(cpf_oa_balances)),
        cash_savings=cash_savings,
        upfront_total=upfront["total"],
        cash_buffer_target=cash_buffer,
        min_cash=flat_price * loan["min_cash_pct"],
    )
    if not elig["eligible"]:
        cash["verdict"] = "ineligible"

    return {
        "request": request,
        "inputs": {
            "household_type": household_type,
            "monthly_household_income": income,
            "ages": ages,
            "average_age_at_loan": average_age_at_loan,
            "income_weighted_age_at_loan": income_weighted_age_at_loan,
            "lender": lender,
            "cpf_oa_total": float(sum(cpf_oa_balances)),
            "cash_savings": cash_savings,
            "flat_price": flat_price,
            "flat_type": flat_type,
        },
        "eligibility": elig,
        "grant": ehg,
        "loan": loan,
        "upfront": upfront,
        "stages": payment_stages(flat_price, flat_type, lender),
        "cash": cash,
        "months_to_close_gap": months_to_close_gap(cash["gap"], monthly_savings) if cash["gap"] else 0,
        "assumptions": [
            f"Policy values as of {policy.as_of()}.",
            "Average gross monthly household income over the past 12 months equals the incomes given.",
            "No other grants (e.g. Proximity Housing Grant does not apply to BTOs).",
            *_loan_assumptions(loan, lender),
            "CPF OA balances are used for the downpayment before cash.",
            f"You should keep {EMERGENCY_BUFFER_MONTHS} months of instalments as emergency cash.",
            "Upfront costs include the option fee, buyer's and mortgage stamp duty, the application fee and a legal estimate.",
        ],
        "warnings": _warnings(ehg),
        "disclaimer": policy.value("meta", "disclaimer"),
    }


def _loan_assumptions(loan: dict, lender: str) -> list[str]:
    msr = policy.value("hdb_loan", "msr")
    if lender == "bank":
        return [
            f"Bank loan at {loan['interest_rate']:.2%} (your input; bank rates change and are not fixed for the "
            f"whole tenure), tenure {loan['tenure_years']} years (bank maximum "
            f"{policy.value('bank_loan', 'max_tenure_years')}).",
            f"LTV {loan['ltv']:.0%} with at least {loan['min_cash_pct']:.0%} of the price paid in cash: LTV drops to "
            f"{policy.value('bank_loan', 'ltv_reduced'):.0%} if the tenure exceeds "
            f"{policy.value('bank_loan', 'ltv_tenure_threshold_years')} years or runs past age "
            f"{policy.value('bank_loan', 'age_limit')} (income-weighted average age).",
            f"Loan size under the {msr:.0%} MSR is assessed at the MAS "
            f"{policy.value('bank_loan', 'assessment_rate_floor'):.1%} interest rate floor.",
        ]
    return [
        f"HDB loan at {policy.value('hdb_loan', 'interest_rate'):.1%}, tenure {loan['tenure_years']} years "
        f"(at most the shorter of {policy.value('hdb_loan', 'max_tenure_years')} years and "
        f"{policy.value('hdb_loan', 'tenure_age_limit')} minus the applicants' average age at key collection).",
        f"Loan size under the {msr:.0%} MSR is assessed at the "
        f"{policy.value('hdb_loan', 'assessment_rate_floor'):.1%} interest rate floor, as HDB does.",
    ]


def _warnings(ehg: dict) -> list[str]:
    w: list[str] = []
    if policy.is_stale():
        w.append(f"Policy file is older than {policy.value('meta', 'stale_after_days')} days. Re-check HDB rules.")
    if ehg.get("verified") is False:
        w.append("The EHG table used here is not yet verified. Confirm the grant with HDB.")
    unverified = policy.unverified_items()
    if unverified:
        w.append("Some values are placeholders to confirm: " + ", ".join(unverified))
    return w
