"""Unit tests with hand-checked expected values."""
import pytest

from calculators import (
    buyer_stamp_duty,
    cash_gap,
    check_eligibility,
    get_ehg_grant,
    get_project_price,
    loan_tenure,
    max_loan,
    monthly_instalment,
    mortgage_stamp_duty,
    upfront_costs,
    months_to_close_gap,
)
from calculators import policy


# ---------- policy file sanity ----------

def test_ehg_family_bands_are_decreasing_and_reach_ceiling():
    bands = policy.node("ehg", "family")["bands"]
    grants = [b["grant"] for b in bands]
    assert grants == sorted(grants, reverse=True)
    assert bands[-1]["max_income"] == policy.node("ehg", "family")["income_ceiling"] == 9000
    assert bands[0]["grant"] == 120000


def test_core_loan_rules_are_verified():
    for key in ("interest_rate", "assessment_rate_floor", "ltv", "msr", "max_tenure_years", "tenure_age_limit"):
        assert policy.node("hdb_loan", key)["verified"] is True


def test_income_ceiling_is_post_ndr_2026():
    assert policy.value("income_ceilings", "family") == 16000
    assert policy.value("hdb_loan", "ltv") == 0.75  # not the outdated 80%


# ---------- EHG ----------

@pytest.mark.parametrize(
    "income, expected",
    [(0, 120000), (1500, 120000), (1501, 110000), (4000, 80000), (8000, 20000),
     (8500, 10000), (9000, 5000), (9001, 0), (15000, 0)],
)
def test_ehg_family_bands(income, expected):
    assert get_ehg_grant("family", income)["grant"] == expected


def test_ehg_second_timers_get_none():
    assert get_ehg_grant("family", 3000, first_timers=False)["grant"] == 0


def test_ehg_singles_half_scale_and_flagged():
    r = get_ehg_grant("single", 4000)  # half of family $8,000 band -> $10,000
    assert r["grant"] == 10000
    assert r["verified"] is False
    assert get_ehg_grant("single", 4600)["grant"] == 0


# ---------- eligibility ----------

def test_family_under_new_ceiling_is_eligible():
    assert check_eligibility("family", 15500, [27, 28])["eligible"] is True


def test_family_over_ceiling_is_not():
    r = check_eligibility("family", 16001, [27, 28])
    assert r["eligible"] is False
    assert "ceiling" in r["reasons"][0]


def test_single_under_35_is_not_eligible():
    assert check_eligibility("single", 4000, [30])["eligible"] is False


def test_single_35_within_ceiling_is_eligible():
    assert check_eligibility("single", 7900, [35])["eligible"] is True


# ---------- loan ----------

def test_monthly_instalment_hand_checked():
    # $400,000 at 2.6% over 25 years: r = 0.026/12, n = 300 -> $1,814.67
    assert monthly_instalment(400000, 0.026, 25) == pytest.approx(1814.67, abs=0.5)


def test_zero_principal_zero_instalment():
    assert monthly_instalment(0) == 0


# HDB: shortest of 25 years and 65 minus the applicants' average age; fractional years rounded down
@pytest.mark.parametrize("age, years", [(25, 25), (40, 25), (45, 20), (47.5, 17), (60, 5), (66, 0)])
def test_tenure(age, years):
    assert loan_tenure(age) == years


def test_ltv_binds_for_high_income():
    r = max_loan(flat_price=360000, grants=0, monthly_household_income=16000, average_applicant_age_at_loan=30)
    assert r["binding_limit"] == "ltv"
    assert r["loan"] == pytest.approx(270000)


def test_msr_binds_for_single_low_income():
    # HDB sizes the loan at the 3.0% floor: 1200 * (1 - 1.0025^-300) / 0.0025 = $253,051.74.
    # The instalment is then charged at 2.6%: $1,148.02, i.e. 28.7% of $4,000 (under the 30% cap).
    r = max_loan(flat_price=360000, grants=80000, monthly_household_income=4000, average_applicant_age_at_loan=28)
    assert r["binding_limit"] == "msr"
    assert r["assessment_rate"] == 0.03
    assert r["loan"] == pytest.approx(253051.74, abs=1)
    assert r["monthly_instalment"] == pytest.approx(1148.02, abs=0.5)
    assert r["msr_used_pct"] == 28.7


def test_needed_binds_when_grants_are_large():
    r = max_loan(flat_price=200000, grants=120000, monthly_household_income=1500, average_applicant_age_at_loan=30)
    assert r["binding_limit"] in ("needed", "msr")
    assert r["loan"] <= 80000


# ---------- upfront ----------

@pytest.mark.parametrize("price, duty", [(180000, 1800), (360000, 5400), (380000, 6000), (0, 0)])
def test_buyer_stamp_duty(price, duty):
    assert buyer_stamp_duty(price) == pytest.approx(duty)


# 0.4% of the loan, capped at $500: $100,000 -> $400; $125,000 -> $500 (exactly the cap); $270,000 -> $500
@pytest.mark.parametrize("loan, duty", [(100000, 400), (125000, 500), (270000, 500), (0, 0)])
def test_mortgage_stamp_duty(loan, duty):
    assert mortgage_stamp_duty(loan) == pytest.approx(duty)


def test_upfront_costs_tengah_4room_hand_checked():
    # option 2,000 + BSD 5,400 + mortgage duty 500 + application 10 + legal estimate 3,000 = 10,910
    r = upfront_costs(360000, "4-room", loan=270000)
    assert r["total"] == pytest.approx(10910)
    assert upfront_costs(360000, "4-room")["mortgage_stamp_duty"] == 0  # no loan, no mortgage duty


# ---------- cash ----------

def test_cash_gap_waterfall():
    r = cash_gap(flat_price=360000, grants=20000, loan=270000, cpf_oa_total=45000,
                 cash_savings=30000, upfront_total=10400)
    assert r["downpayment"] == 70000
    assert r["from_cpf_oa"] == 45000
    assert r["cash_for_downpayment"] == 25000
    assert r["total_cash_needed"] == 35400
    assert r["gap"] == 5400
    assert r["verdict"] == "gap"


def test_cash_tight_when_below_buffer():
    r = cash_gap(flat_price=360000, grants=20000, loan=270000, cpf_oa_total=70000,
                 cash_savings=12000, upfront_total=10400, cash_buffer_target=7000)
    assert r["gap"] == 0
    assert r["verdict"] == "tight"


def test_months_to_close_gap():
    assert months_to_close_gap(5400, 1000) == 6
    assert months_to_close_gap(0, 1000) == 0
    assert months_to_close_gap(5400, 0) is None


# ---------- project lookup ----------

def test_tengah_price_lookup():
    r = get_project_price("tengah-garden-avenue", "4-room")
    assert r["price_low"] == 360000 and r["status"] == "indicative"


def test_unknown_project_returns_error():
    assert "error" in get_project_price("nowhere")


def test_sourced_items_cover_unverified_items():
    items = policy.sourced_items()
    assert {i["rule"] for i in items if not i["verified"]} == set(policy.unverified_items())
    assert any(i["rule"] == "hdb_loan.assessment_rate_floor" and i["verified"] for i in items)
