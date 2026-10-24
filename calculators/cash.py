"""Where the money comes from, and whether there is a gap."""
from __future__ import annotations

from . import policy


def cash_gap(
    flat_price: float,
    grants: float,
    loan: float,
    cpf_oa_total: float,
    cash_savings: float,
    upfront_total: float = 0.0,
    cpf_buffer: float = 0.0,
    cash_buffer_target: float = 0.0,
    min_cash: float = 0.0,
) -> dict:
    """Waterfall: price - grants - loan = downpayment; CPF OA pays first, then cash; plus upfront costs.

    cpf_buffer: OA you want to keep untouched (e.g. a few months of instalments).
    cash_buffer_target: emergency cash you should still have afterwards. If you can pay but end
    up below this, the verdict is "tight" rather than "affordable".
    min_cash: part of the downpayment that must be paid in cash (bank loans), so CPF cannot cover it.
    """
    downpayment = max(0.0, flat_price - grants - loan)
    usable_oa = max(0.0, cpf_oa_total - cpf_buffer)
    from_cpf = min(max(0.0, downpayment - min_cash), usable_oa)
    cash_for_downpayment = downpayment - from_cpf
    cash_needed = cash_for_downpayment + upfront_total
    gap = max(0.0, cash_needed - cash_savings)
    surplus = max(0.0, cash_savings - cash_needed)

    if gap == 0 and surplus >= cash_buffer_target:
        verdict = "affordable"
    elif gap == 0:
        verdict = "tight"
    else:
        verdict = "gap"

    return {
        "verdict": verdict,
        "downpayment": round(downpayment, 2),
        "from_cpf_oa": round(from_cpf, 2),
        "cash_for_downpayment": round(cash_for_downpayment, 2),
        "upfront_costs": round(upfront_total, 2),
        "total_cash_needed": round(cash_needed, 2),
        "cash_savings": round(cash_savings, 2),
        "gap": round(gap, 2),
        "cash_left_after": round(surplus, 2),
        "cash_buffer_target": round(cash_buffer_target, 2),
        "cpf_oa_left_after": round(usable_oa - from_cpf + cpf_buffer, 2),
    }


def months_to_close_gap(gap: float, monthly_savings: float) -> int | None:
    if gap <= 0:
        return 0
    if monthly_savings <= 0:
        return None
    return int(-(-gap // monthly_savings))  # ceiling division


def payment_stages(flat_price: float, flat_type: str, lender: str = "hdb", deferred: bool = False) -> dict:
    """When money is due for a new flat: option fee at booking, downpayment at signing, the rest at key collection.

    The option fee counts towards the signing downpayment. Grants are not included in these amounts.
    """
    option_fee = policy.node("upfront", "option_fee")["by_flat_type"].get(flat_type.lower(), 0)
    pcts = policy.node("payment_stages", "downpayment_at_signing")
    pct = pcts["deferred_income_assessment"] if deferred else pcts["bank_loan" if lender == "bank" else "hdb_loan"]
    signing_total = flat_price * pct
    return {
        "booking_option_fee": option_fee,
        "signing_pct": pct,
        "signing_downpayment": round(signing_total, 2),
        "signing_after_option_fee": round(max(0.0, signing_total - option_fee), 2),
        "note": "Balance (after grants and loan) is due at key collection, when the loan is disbursed.",
    }
