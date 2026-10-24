"""Unit tests with hand-checked expected values."""
import pytest

from calculators import (
    assess_household,
    bank_loan_terms,
    buyer_stamp_duty,
    cash_gap,
    check_eligibility,
    default_bank_tenure,
    get_ehg_grant,
    get_project_price,
    list_projects,
    loan_tenure,
    max_loan,
    monthly_instalment,
    months_to_close_gap,
    mortgage_stamp_duty,
    payment_stages,
    upfront_costs,
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


def test_ehg_singles_verified():
    r = get_ehg_grant("single", 4000)  # HDB singles table: $3,751-$4,000 -> $10,000
    assert r["grant"] == 10000
    assert r["verified"] is True
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
    assert r["price_low"] == 360000 and r["status"] == "upcoming"
    assert "estimate" in r["price_basis"]


def test_unknown_project_returns_error():
    assert "error" in get_project_price("nowhere")


def test_sourced_items_cover_unverified_items():
    items = policy.sourced_items()
    assert {i["rule"] for i in items if not i["verified"]} == set(policy.unverified_items())
    assert any(i["rule"] == "hdb_loan.assessment_rate_floor" and i["verified"] for i in items)


def test_singles_ehg_table_is_half_scale_of_family():
    # HDB's singles PDF: every band is the family band at half the income and half the grant
    family, single = policy.node("ehg", "family")["bands"], policy.node("ehg", "single")["bands"]
    assert [(b["max_income"] * 2, b["grant"] * 2) for b in single] == [(b["max_income"], b["grant"]) for b in family]


@pytest.mark.parametrize("income, grant", [(750, 60000), (751, 55000), (4000, 10000), (4500, 2500), (4501, 0)])
def test_singles_ehg_bands_hand_checked(income, grant):
    assert get_ehg_grant("single", income)["grant"] == grant


@pytest.mark.parametrize("flat_type, fee", [("2-room", 500), ("3-room", 1000), ("4-room", 2000), ("5-room", 2000)])
def test_option_fee_matches_hdb_annex_b(flat_type, fee):
    assert upfront_costs(300000, flat_type)["option_fee"] == fee



# ---------- projects (HDB Annex A, Feb and Jun 2026) ----------

@pytest.mark.parametrize("pid, flat_type, point, price", [
    ("kim-keat-crest", "4-room", "low", 455000),     # Feb 2026 Annex A
    ("berlayar-rise", "4-room", "high", 810000),     # Jun 2026 Annex A
    ("sembawang-brook", "3gen", "low", 468000),
    ("sembawang-voyage", "2-room", "high", 228000),  # Type 2 (48 sqm) top of range
])
def test_launched_project_prices_match_hdb_annex(pid, flat_type, point, price):
    r = get_project_price(pid, flat_type, point)
    assert r["price_used"] == price and r["status"] == "launched"


def test_upcoming_project_uses_named_comparable():
    r = get_project_price("bedok-bayshore-2", "3-room")
    assert r["price_low"] == 356000                  # Kim Keat Crest 3-room
    assert "Kim Keat Crest" in r["price_basis"]
    assert get_project_price("tengah-garden-avenue", "5-room")["price_low"] == 420000  # Sembawang Brook


def test_flat_type_not_offered_is_an_error():
    assert "error" in get_project_price("tampines-bliss", "2-room")


def test_list_projects_covers_all_regions():
    projects = list_projects()
    assert len(projects) == 20
    assert {p["region"] for p in projects} == {"North", "North-East", "East", "West", "Central"}
    assert sum(p["units"] for p in projects if p["exercise"] == "June 2026 BTO") == 6952  # HDB's total


# ---------- bank loans (MAS) and loan choices ----------

def test_bank_loan_terms_full_and_reduced_ltv():
    assert bank_loan_terms(25, 30) == {"ltv": 0.75, "min_cash_pct": 0.05, "reduced": False}
    assert bank_loan_terms(30, 30)["ltv"] == 0.55          # tenure over 25 years
    assert bank_loan_terms(25, 41)["min_cash_pct"] == 0.10  # 41 + 25 runs past 65
    assert default_bank_tenure(29.4375) == 25 and default_bank_tenure(45) == 20


def test_bank_loan_hand_checked():
    # $8,000 couple, $360k flat, grant $20k, 1.6% bank rate, 25 years. MSR limit at the 4% MAS floor:
    # 2400 * (1 - (1 + 0.04/12)^-300) / (0.04/12) = $454,685.96 > LTV 270,000, so LTV binds.
    # Instalment 270,000 at 1.6% over 300 months = $1,092.56; total interest 1,092.56 x 300 - 270,000 = $57,768.
    r = max_loan(360000, 20000, 8000, 29.5, lender="bank", bank_rate=0.016, income_weighted_age_at_loan=29.4375)
    assert r["assessment_rate"] == 0.04
    assert r["limit_msr"] == pytest.approx(454685.96, abs=1)
    assert r["loan"] == 270000 and r["binding_limit"] == "ltv"
    assert r["monthly_instalment"] == pytest.approx(1092.56, abs=0.5)
    assert r["total_interest"] == pytest.approx(57768, abs=150)
    assert r["min_cash_pct"] == 0.05


def test_bank_30_year_tenure_drops_ltv_to_55():
    r = max_loan(360000, 20000, 8000, 29.5, lender="bank", bank_rate=0.016, tenure_years=30)
    assert r["loan"] == pytest.approx(198000)    # 55% x 360,000
    assert r["min_cash_pct"] == 0.10


def test_choosing_to_borrow_less():
    r = max_loan(360000, 20000, 8000, 30, desired_loan=200000)
    assert r["loan"] == 200000 and r["binding_limit"] == "chosen"
    assert r["max_loan"] == 270000


def test_shorter_hdb_tenure_shrinks_msr_loan():
    # 1200 * (1 - 1.0025^-240) / 0.0025 = $216,373.10 over 20 years at the 3% floor
    r = max_loan(360000, 80000, 4000, 28, tenure_years=20)
    assert r["tenure_years"] == 20
    assert r["loan"] == pytest.approx(216373.10, abs=1)


def test_tenure_cannot_exceed_hdb_maximum():
    assert max_loan(360000, 0, 8000, 50, tenure_years=25)["tenure_years"] == 15  # 65 - 50


def test_bank_min_cash_downpayment():
    # downpayment 70,000; 5% of 360,000 = 18,000 must be cash even with 70,000 in CPF OA
    r = cash_gap(flat_price=360000, grants=20000, loan=270000, cpf_oa_total=70000, cash_savings=50000,
                 min_cash=18000)
    assert r["from_cpf_oa"] == 52000 and r["cash_for_downpayment"] == 18000


def test_payment_stages_hand_checked():
    hdb = payment_stages(360000, "4-room", "hdb")
    assert hdb["signing_downpayment"] == 36000 and hdb["signing_after_option_fee"] == 34000
    assert payment_stages(360000, "4-room", "bank")["signing_downpayment"] == 72000
    assert payment_stages(360000, "4-room", deferred=True)["signing_downpayment"] == 9000


def test_assess_household_bank_uses_income_weighted_age():
    r = assess_household(household_type="family", incomes=[4500, 3500], ages=[25, 26], cpf_oa_balances=[45000],
                         cash_savings=50000, flat_price=360000, years_until_key_collection=4, lender="bank",
                         bank_rate=0.016)
    assert r["inputs"]["income_weighted_age_at_loan"] == pytest.approx(29.4375)
    assert r["loan"]["monthly_instalment"] == pytest.approx(1092.56, abs=0.5)
    assert any("Bank loan" in x for x in r["assumptions"])


def test_request_round_trips_for_what_ifs():
    r = assess_household(household_type="family", incomes=[4500, 3500], ages=[25, 26], cpf_oa_balances=[45000],
                         cash_savings=50000, flat_price=360000, years_until_key_collection=4)
    bank = assess_household(**{**r["request"], "lender": "bank", "bank_rate": 0.016})
    assert bank["loan"]["lender"] == "bank" and bank["inputs"]["flat_price"] == 360000
