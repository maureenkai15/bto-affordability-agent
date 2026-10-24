"""Plain-English words around the numbers: a 'what this means' summary and a jargon buster.

Only formats results from the calculators and values from policy_2026.yaml; no maths here.
"""
from __future__ import annotations

from calculators import policy

from .theme import money


def plain_summary(a: dict) -> list[str]:
    """Four or five short sentences a first-time buyer can read without knowing any jargon."""
    loan, cash, grant = a["loan"], a["cash"], a["grant"]
    if cash["verdict"] == "ineligible":
        return [*a["eligibility"]["reasons"], "Nothing else applies until the household is eligible."]
    lender = "the bank" if loan.get("lender") == "bank" else "HDB"
    out = []
    if grant["grant"]:
        out.append(f"The government gives you a {money(grant['grant'])} housing grant, paid into CPF, because of "
                   f"your income ({grant['band']}).")
    else:
        out.append("You don't get the Enhanced CPF Housing Grant at this income.")
    if loan["loan"] and loan["msr_used_pct"] is not None:
        out.append(f"You'd borrow {money(loan['loan'])} from {lender} and repay {money(loan['monthly_instalment'])} "
                   f"a month for {loan['tenure_years']} years, about {loan['msr_used_pct']:.0f}% of your income. "
                   f"This can be paid from CPF OA, cash or both.")
    else:
        out.append("You wouldn't get a loan with these details, so the whole price after grants is paid upfront.")
    out.append(f"The rest of the price, {money(cash['downpayment'])}, is your downpayment: "
               f"{money(cash['from_cpf_oa'])} from CPF OA and {money(cash['cash_for_downpayment'])} in cash.")
    extra = f" plus your {money(cash['renovation'])} renovation budget" if cash.get("renovation") else ""
    out.append(f"On top of that you pay about {money(cash['upfront_costs'])} in fees and stamp duty{extra}, in cash.")
    if cash["gap"]:
        months = a.get("months_to_close_gap")
        out.append(f"That's {money(cash['gap'])} more cash than you have"
                   + (f"; saving at your current rate closes it in about {months} months." if months else "."))
    else:
        out.append(f"Afterwards you'd still have {money(cash['cash_left_after'])} in cash.")
    return out


def jargon() -> list[tuple[str, str]]:
    p = policy.value
    return [
        ("BTO", "Build-To-Order: a new HDB flat you apply for before it's built, then wait a few years for keys."),
        ("HFE letter", "HDB Flat Eligibility letter. You need it before applying; it states the grants and HDB loan "
                       "you can get. It is the official answer this tool estimates."),
        ("EHG", f"Enhanced CPF Housing Grant: up to {money(policy.node('ehg', 'family')['bands'][0]['grant'])} for "
                f"first-timer families earning up to {money(policy.node('ehg', 'family')['income_ceiling'])} a month. "
                "Lower income, bigger grant."),
        ("CPF OA", "Your CPF Ordinary Account. It can pay the downpayment and monthly instalments, not renovation."),
        ("LTV", f"Loan-to-value: the most you can borrow as a share of the price, {p('hdb_loan', 'ltv'):.0%} for "
                "HDB and bank loans."),
        ("MSR", f"Mortgage Servicing Ratio: the monthly instalment can't exceed {p('hdb_loan', 'msr'):.0%} of your "
                "gross monthly income."),
        ("TDSR", f"Total Debt Servicing Ratio: for bank loans, all your debt repayments together can't exceed "
                 f"{p('bank_loan', 'tdsr'):.0%} of income."),
        ("Stress-test rate", f"Lenders size your loan as if the rate were higher ({p('hdb_loan', 'assessment_rate_floor'):.0%} "
                             f"for HDB, {p('bank_loan', 'assessment_rate_floor'):.0%} for banks), so you can cope if "
                             "rates rise. You still pay the actual rate."),
        ("Tenure", "How many years you take to repay the loan. Longer means smaller instalments but more interest."),
        ("Option fee", "A small fee paid when you book your flat. It counts towards your downpayment."),
        ("Downpayment", "The part of the price not covered by the grant and loan, paid from CPF OA and cash."),
        ("Standard / Plus / Prime", "HDB's project types. Plus and Prime flats are in more central or popular spots "
                                    "and come with extra conditions, such as a longer minimum occupation period."),
    ]
