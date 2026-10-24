"""Tool schemas the model sees, and the dispatcher that runs the real Python calculators."""
from __future__ import annotations

import json
from typing import Any, Callable

from calculators import (
    assess_household,
    cash_gap,
    check_eligibility,
    get_ehg_grant,
    get_project_price,
    max_loan,
    upfront_costs,
)

_HOUSEHOLD = {"type": "string", "enum": ["family", "single"],
              "description": "'family' for couples/fiance(e)s/families, 'single' for singles 35+."}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_project_price",
        "description": "Look up indicative BTO prices for a known project. Use before any maths that needs a flat price, "
                       "unless the user gives a price. Known project ids: 'tengah-garden-avenue'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "string"},
                "flat_type": {"type": "string", "description": "e.g. '4-room'"},
                "point": {"type": "string", "enum": ["low", "high"], "description": "Which end of the range to use."},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "check_eligibility",
        "description": "Check if the household can buy a new BTO and take an HDB loan (income ceiling, age for singles).",
        "input_schema": {
            "type": "object",
            "properties": {
                "household_type": _HOUSEHOLD,
                "monthly_household_income": {"type": "number", "description": "Combined gross monthly income, SGD."},
                "applicant_ages": {"type": "array", "items": {"type": "integer"}},
                "all_singapore_citizens": {"type": "boolean"},
                "first_timers": {"type": "boolean"},
            },
            "required": ["household_type", "monthly_household_income", "applicant_ages"],
        },
    },
    {
        "name": "get_ehg_grant",
        "description": "Get the Enhanced CPF Housing Grant amount for an average gross monthly household income.",
        "input_schema": {
            "type": "object",
            "properties": {
                "household_type": _HOUSEHOLD,
                "monthly_household_income": {"type": "number"},
                "first_timers": {"type": "boolean"},
            },
            "required": ["household_type", "monthly_household_income"],
        },
    },
    {
        "name": "max_loan",
        "description": "Largest HDB loan: the smallest of the 75% LTV cap, the 30% mortgage servicing ratio "
                       "(assessed at HDB's interest rate floor), and price minus grants. "
                       "Also returns tenure and monthly instalment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flat_price": {"type": "number"},
                "grants": {"type": "number"},
                "monthly_household_income": {"type": "number"},
                "average_applicant_age_at_loan": {"type": "number",
                                                  "description": "Average age of the applicants at key collection."},
            },
            "required": ["flat_price", "grants", "monthly_household_income", "average_applicant_age_at_loan"],
        },
    },
    {
        "name": "upfront_costs",
        "description": "One-off costs: option fee, buyer's stamp duty, mortgage stamp duty, application fee, "
                       "legal/misc estimate.",
        "input_schema": {
            "type": "object",
            "properties": {"flat_price": {"type": "number"}, "flat_type": {"type": "string"},
                           "loan": {"type": "number", "description": "HDB loan amount, for mortgage stamp duty."}},
            "required": ["flat_price"],
        },
    },
    {
        "name": "cash_gap",
        "description": "Waterfall of price - grants - loan = downpayment, paid by CPF OA first then cash, "
                       "plus upfront costs. Returns the cash gap and a verdict.",
        "input_schema": {
            "type": "object",
            "properties": {
                "flat_price": {"type": "number"},
                "grants": {"type": "number"},
                "loan": {"type": "number"},
                "cpf_oa_total": {"type": "number"},
                "cash_savings": {"type": "number"},
                "upfront_total": {"type": "number"},
                "cash_buffer_target": {"type": "number",
                                       "description": "Emergency cash to keep; use 6x the monthly instalment."},
            },
            "required": ["flat_price", "grants", "loan", "cpf_oa_total", "cash_savings"],
        },
    },
    {
        "name": "assess_household",
        "description": "Run the complete assessment in one call once ALL inputs are known. Prefer this for a final "
                       "answer; use the single tools to explain a step or answer a what-if.",
        "input_schema": {
            "type": "object",
            "properties": {
                "household_type": _HOUSEHOLD,
                "incomes": {"type": "array", "items": {"type": "number"},
                            "description": "Each applicant's gross monthly income."},
                "ages": {"type": "array", "items": {"type": "integer"}},
                "cpf_oa_balances": {"type": "array", "items": {"type": "number"}},
                "cash_savings": {"type": "number"},
                "flat_price": {"type": "number"},
                "flat_type": {"type": "string"},
                "years_until_key_collection": {"type": "integer"},
                "monthly_savings": {"type": "number"},
                "all_singapore_citizens": {"type": "boolean"},
                "first_timers": {"type": "boolean"},
            },
            "required": ["household_type", "incomes", "ages", "cpf_oa_balances", "cash_savings", "flat_price"],
        },
    },
]

_DISPATCH: dict[str, Callable[..., dict]] = {
    "get_project_price": get_project_price,
    "check_eligibility": check_eligibility,
    "get_ehg_grant": get_ehg_grant,
    "max_loan": max_loan,
    "upfront_costs": upfront_costs,
    "cash_gap": cash_gap,
    "assess_household": assess_household,
}


def run_tool(name: str, tool_input: dict[str, Any]) -> tuple[dict, bool]:
    """Execute a tool. Returns (result, is_error). Errors go back to the model so it can fix its inputs."""
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"Unknown tool {name}"}, True
    try:
        return fn(**tool_input), False
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}, True
    except Exception as e:  # noqa: BLE001 - surface any calculator error to the model
        return {"error": f"{type(e).__name__}: {e}"}, True


def to_json(result: dict) -> str:
    return json.dumps(result, default=str)
