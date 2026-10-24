"""Pure, tested calculators. The LLM never does arithmetic; it calls these."""
from .assess import assess_household, get_project_price
from .cash import cash_gap, months_to_close_gap
from .eligibility import check_eligibility
from .grants import get_ehg_grant
from .loan import loan_tenure, max_loan, monthly_instalment
from .upfront import buyer_stamp_duty, upfront_costs

__all__ = [
    "assess_household",
    "buyer_stamp_duty",
    "cash_gap",
    "check_eligibility",
    "get_ehg_grant",
    "get_project_price",
    "loan_tenure",
    "max_loan",
    "monthly_instalment",
    "months_to_close_gap",
    "upfront_costs",
]
