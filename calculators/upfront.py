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


def upfront_costs(flat_price: float, flat_type: str = "4-room") -> dict:
    option_fee = policy.node("upfront", "option_fee")["by_flat_type"].get(flat_type.lower(), 0)
    stamp = buyer_stamp_duty(flat_price)
    legal = policy.value("upfront", "legal_and_misc_estimate")
    return {
        "option_fee": option_fee,
        "buyer_stamp_duty": stamp,
        "legal_and_misc_estimate": legal,
        "total": round(option_fee + stamp + legal, 2),
        "note": "Option fee, stamp duty and legal figures are placeholders to confirm with HDB/IRAS.",
    }
