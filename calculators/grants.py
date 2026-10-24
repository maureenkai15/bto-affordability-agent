"""Enhanced CPF Housing Grant (EHG) lookup."""
from __future__ import annotations

from . import policy


def _family_bands() -> list[dict]:
    return policy.node("ehg", "family")["bands"]


def _single_bands() -> list[dict]:
    """Singles table = family table at half the income bands and half the grant (assumption, flagged)."""
    return [{"max_income": b["max_income"] / 2, "grant": b["grant"] / 2} for b in _family_bands()]


def get_ehg_grant(household_type: str, monthly_household_income: float, first_timers: bool = True) -> dict:
    """Return the EHG amount for an average gross monthly household income."""
    if not first_timers:
        return {
            "grant": 0,
            "band": None,
            "explanation": "EHG here assumes first-timers. Second-timer rules differ; check with HDB.",
            "verified": True,
        }

    cfg = policy.node("ehg", household_type)
    bands = _family_bands() if household_type == "family" else _single_bands()
    ceiling = cfg["income_ceiling"]

    if monthly_household_income > ceiling:
        return {
            "grant": 0,
            "band": f"above ${ceiling:,.0f}",
            "explanation": f"No EHG: income is above the ${ceiling:,.0f}/month EHG ceiling.",
            "verified": cfg.get("verified", True),
            "source_url": cfg["source_url"],
        }

    lower = 0.0
    for b in bands:
        if monthly_household_income <= b["max_income"]:
            grant = int(b["grant"])
            band = f"${lower:,.0f} to ${b['max_income']:,.0f}" if lower else f"up to ${b['max_income']:,.0f}"
            return {
                "grant": grant,
                "band": band,
                "explanation": f"Income band {band} gets an EHG of ${grant:,}.",
                "verified": cfg.get("verified", True),
                "source_url": cfg["source_url"],
            }
        lower = b["max_income"] + 1

    raise ValueError("EHG bands do not cover the income ceiling - check policy_2026.yaml")
