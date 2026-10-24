"""Eight real-life households. Each checks the verdict and the one thing the tool must get right."""
import pytest

from calculators import assess_household

TENGAH_4RM = 360000


def run(**kw):
    defaults = dict(household_type="family", flat_price=TENGAH_4RM, flat_type="4-room")
    defaults.update(kw)
    return assess_household(**defaults)


def test_1_typical_couple_25_dual_income():
    r = run(incomes=[4500, 3500], ages=[25, 26], cpf_oa_balances=[25000, 20000], cash_savings=50000)
    assert r["grant"]["grant"] == 20000            # $7,501-$8,000 band
    assert r["loan"]["binding_limit"] == "ltv"     # 75% of price
    assert r["cash"]["verdict"] == "affordable"


def test_2_just_above_ehg_cliff():
    r = run(incomes=[5000, 4200], ages=[27, 27], cpf_oa_balances=[30000, 30000], cash_savings=40000)
    assert r["inputs"]["monthly_household_income"] == 9200
    assert r["grant"]["grant"] == 0
    assert "above" in r["grant"]["explanation"]


def test_3_eligible_only_under_new_16k_ceiling():
    r = run(incomes=[8000, 7500], ages=[29, 30], cpf_oa_balances=[60000, 55000], cash_savings=60000)
    assert r["eligibility"]["eligible"] is True    # would fail the old $14,000 ceiling
    assert r["cash"]["verdict"] in ("affordable", "tight")


def test_4_above_ceiling_is_ineligible():
    r = run(incomes=[9000, 8000], ages=[30, 31], cpf_oa_balances=[80000, 70000], cash_savings=100000)
    assert r["eligibility"]["eligible"] is False
    assert r["cash"]["verdict"] == "ineligible"


def test_5_one_income_msr_binds():
    r = run(incomes=[4000, 0], ages=[28, 27], cpf_oa_balances=[30000, 0], cash_savings=20000)
    assert r["grant"]["grant"] == 80000
    assert r["loan"]["binding_limit"] == "msr"
    assert r["loan"]["msr_used_pct"] == pytest.approx(30.0, abs=0.1)


def test_6_single_35_plus():
    r = run(household_type="single", incomes=[4000], ages=[36], cpf_oa_balances=[60000], cash_savings=30000)
    assert r["eligibility"]["eligible"] is True
    assert any("Singles EHG" in w for w in r["warnings"])


def test_7_citizen_plus_pr_is_flagged():
    r = run(incomes=[5000, 3000], ages=[28, 28], cpf_oa_balances=[30000, 20000], cash_savings=40000,
            all_singapore_citizens=False)
    assert any("citizenship" in n.lower() for n in r["eligibility"]["notes"])


@pytest.mark.parametrize("oa, cash, cpf_part", [(5000, 90000, 5000), (90000, 15000, 70000)])
def test_8_low_oa_vs_high_oa(oa, cash, cpf_part):
    r = run(incomes=[4500, 3500], ages=[26, 26], cpf_oa_balances=[oa], cash_savings=cash)
    assert r["cash"]["downpayment"] == 70000
    assert r["cash"]["from_cpf_oa"] == cpf_part


def test_older_buyer_gets_shorter_tenure_after_wait():
    r = run(incomes=[5000, 4000], ages=[44, 42], cpf_oa_balances=[80000, 60000], cash_savings=50000,
            years_until_key_collection=4)
    assert r["loan"]["tenure_years"] == 17       # 65 - (44 + 4)
