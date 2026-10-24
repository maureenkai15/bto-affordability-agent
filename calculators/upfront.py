"""One-off costs on top of the downpayment."""
from __future__ import annotations

from . import policy


def buyer_stamp_duty(price: float) -> float:
    """Marginal tiers from policy_2026.yaml."""
    duty, lower = 0.0, 0.0
    for tier in policy.node("upfront", "buyer_stamp_duty")["tiers"]:
        upper = tier["up_to"] if tier["up_to"] is not None else float("inf")
        if price > lower:
            duty += (min(price, upper) - lower) * tier["rate"]
        lower = upper
    return round(duty, 2)


def mortgage_stamp_duty(loan: float) -> float:
    """Stamp duty on the mortgage: a rate on the loan granted, capped. Zero without a loan."""
    cfg = policy.node("upfront", "mortgage_stamp_duty")
    return round(min(max(loan, 0.0) * cfg["rate"], cfg["max"]), 2)


def upfront_costs(flat_price: float, flat_type: str = "4-room", loan: float = 0.0) -> dict:
    option_fee = policy.node("upfront", "option_fee")["by_flat_type"].get(flat_type.lower(), 0)
    stamp = buyer_stamp_duty(flat_price)
    mortgage_stamp = mortgage_stamp_duty(loan)
    application_fee = policy.value("upfront", "application_fee")
    legal = policy.value("upfront", "legal_and_misc_estimate")
    return {
        "option_fee": option_fee,
        "buyer_stamp_duty": stamp,
        "mortgage_stamp_duty": mortgage_stamp,
        "application_fee": application_fee,
        "legal_and_misc_estimate": legal,
        "total": round(option_fee + stamp + mortgage_stamp + application_fee + legal, 2),
        "note": "Option fee and legal figures are placeholders to confirm with HDB.",
    }
