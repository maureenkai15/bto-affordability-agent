"""CPF projection, TDSR and renovation budget, with hand-checked values (CPF rates from 1 Jan 2026)."""
import pytest

from calculators import assess_household, cpf_oa_monthly, max_loan, project_household

COUPLE = dict(household_type="family", incomes=[4500, 3500], ages=[25, 26], cpf_oa_balances=[25000, 20000],
              cash_savings=50000, flat_price=360000, years_until_key_collection=4, monthly_savings=2000)


@pytest.mark.parametrize("wage, age, oa", [
    (4500, 29, 1035.13),   # 4,500 x 37% x 0.6217
    (9000, 30, 1840.23),   # capped at the $8,000 Ordinary Wage ceiling
    (4000, 40, 840.20),    # above 35-45: 37% x 0.5677
    (700, 30, 0),          # $750 and below: not projected
])
def test_cpf_oa_monthly_hand_checked(wage, age, oa):
    assert cpf_oa_monthly(wage, age) == pytest.approx(oa, abs=0.01)


def test_projection_one_year_hand_checked():
    # OA: 45,000 x 1.025 + 12 x (1,035.13 + 805.10) = 68,207.76; cash: 50,000 + 12 x 2,000 = 74,000
    now, later = project_household(COUPLE, years=1)
    assert now["cpf_oa_total"] == 45000 and now["verdict"] == "affordable"
    assert later["cpf_oa_total"] == pytest.approx(68207.76, abs=0.01)
    assert later["cash_savings"] == 74000


def test_pay_rise_can_cost_the_grant():
    # $8,900 gets a $5,000 EHG; 3% a year later it is $9,167, above the $9,000 EHG ceiling
    r = project_household({**COUPLE, "incomes": [4500, 4400]}, years=1, income_growth=0.03)
    assert r[0]["grant"] == 5000 and r[1]["grant"] == 0


def test_price_growth_applies_each_year():
    r = project_household(COUPLE, years=2, price_growth=0.05)
    assert r[2]["flat_price"] == pytest.approx(396900)   # 360,000 x 1.05^2


def test_tdsr_with_other_debts_binds_bank_loan():
    # 55% x 8,000 - 3,000 debts = 1,400/month at the 4% floor over 25 years = $265,233.48 (< 75% LTV 270,000)
    r = max_loan(360000, 20000, 8000, 29.5, lender="bank", bank_rate=0.016, other_monthly_debts=3000)
    assert r["binding_limit"] == "tdsr"
    assert r["loan"] == pytest.approx(265233.48, abs=1)


def test_other_debts_do_not_change_hdb_loan():
    assert max_loan(360000, 20000, 8000, 30, other_monthly_debts=3000)["loan"] == 270000


def test_renovation_budget_is_paid_in_cash():
    # total cash needed 35,910 + 20,000 renovation = 55,910 > 50,000 savings -> gap 5,910
    r = assess_household(**{k: v for k, v in COUPLE.items() if k != "monthly_savings"}, renovation_budget=20000)
    assert r["cash"]["total_cash_needed"] == 55910
    assert r["cash"]["gap"] == 5910 and r["cash"]["verdict"] == "gap"
