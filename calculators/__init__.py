"""Pure, tested calculators. The LLM never does arithmetic; it calls these."""
from .assess import assess_household, get_project_price, list_projects
from .cash import cash_gap, months_to_close_gap, payment_stages
from .eligibility import check_eligibility
from .grants import get_ehg_grant
from .loan import bank_loan_terms, default_bank_tenure, loan_tenure, max_loan, monthly_instalment
from .projection import cpf_oa_monthly, project_household
from .upfront import buyer_stamp_duty, mortgage_stamp_duty, upfront_costs

__all__ = [
    "assess_household",
    "bank_loan_terms",
    "buyer_stamp_duty",
    "cash_gap",
    "check_eligibility",
    "cpf_oa_monthly",
    "default_bank_tenure",
    "get_ehg_grant",
    "get_project_price",
    "list_projects",
    "loan_tenure",
    "max_loan",
    "monthly_instalment",
    "months_to_close_gap",
    "mortgage_stamp_duty",
    "payment_stages",
    "project_household",
    "upfront_costs",
]
