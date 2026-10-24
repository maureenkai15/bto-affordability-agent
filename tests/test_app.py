"""Streamlit app in free form mode: no API key, and the Anthropic client must never be created."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import agent.agent
from agent import has_api_key

APP = Path(__file__).resolve().parent.parent / "app.py"


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # present but empty, so .env / secrets are not loaded

    def forbidden(*a, **kw):
        raise AssertionError("Anthropic client created in form mode")

    monkeypatch.setattr(agent.agent, "Anthropic", forbidden)


def start():
    at = AppTest.from_file(str(APP), default_timeout=30)
    at.run()
    assert not at.exception
    return at


def click(at, label):
    next(b for b in at.button if b.label == label).click()
    at.run()
    assert not at.exception
    return at


def verdict_html(at):
    return next(m.value for m in at.markdown if 'class="verdict"' in m.value)


@pytest.mark.parametrize("key, expected", [
    ("", False), ("sk-ant-...", False), ("not-a-key", False), ("sk-ant-api03-abc123", True),
])
def test_has_api_key(monkeypatch, key, expected):
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    assert has_api_key() is expected


def test_chat_mode_disabled_without_key(no_key):
    at = start()
    assert at.sidebar.radio[0].disabled
    assert at.sidebar.radio[0].value == "Calculator (free)"


def test_opens_on_a_filled_in_example(no_key):
    at = start()
    assert "Affordable" in verdict_html(at)


def test_example_couple_hand_checked(no_key):
    at = click(start(), "👫  Couple, 25 & 26 · $8k")
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Grant (EHG)"] == "$20,000"     # $7,501-$8,000 band
    assert metrics["HDB loan"] == "$270,000"       # 75% LTV of $360,000
    # cash left = 50,000 - (25,000 downpayment after CPF + 10,910 upfront)
    assert metrics["Cash left after buying"] == "$14,090"
    assert "Affordable" in verdict_html(at)


def test_example_one_income_msr_binds(no_key):
    at = click(start(), "💼  One income · $4k")
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Grant (EHG)"] == "$80,000"         # $3,501-$4,000 band
    assert metrics["HDB loan"] == "$253,052"           # 30% x $4,000 sized at the 3.0% floor
    assert metrics["Monthly instalment"] == "$1,148"   # same loan paid at 2.6%
    assert any("30% mortgage servicing ratio" in c.value for c in at.caption)


def test_example_single_hand_checked(no_key):
    at = click(start(), "🧑  Single, 36 · $4k")
    assert verdict_html(at)
    assert {m.label: m.value for m in at.metric}["Grant (EHG)"] == "$10,000"  # singles $3,751-$4,000 band
    assert at.warning  # the legal fee estimate is still flagged


def test_sliders_update_live(no_key):
    at = start()
    next(s for s in at.slider if s.key == "f_inc1").set_value(9000).run()  # couple now at $12,500
    assert {m.label: m.value for m in at.metric}["Grant (EHG)"] == "$0"  # above the $9,000 EHG ceiling


def test_start_over_restores_defaults(no_key):
    at = click(start(), "💼  One income · $4k")
    at = click(at, "↺  Start over")
    assert {m.label: m.value for m in at.metric}["HDB loan"] == "$270,000"


def test_picking_a_project_sets_hdb_price(no_key):
    at = start()
    at.selectbox(key="f_project").set_value("kim-keat-crest").run()
    assert not at.exception
    assert at.session_state["f_flat_type"] == "4-room"
    assert at.slider(key="f_price").value == 455000            # HDB Feb 2026 Annex A, 4-room low end


def test_bank_loan_hand_checked(no_key):
    at = start()
    at.session_state["f_lender"] = "bank"
    at.session_state["f_bank_rate"] = 1.6
    at.run()
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Bank loan"] == "$270,000"                  # 75% LTV binds
    assert metrics["Monthly instalment"] == "$1,093"           # 270,000 at 1.6% over 25 years = 1,092.56


def test_bank_30_year_tenure_drops_ltv(no_key):
    at = start()
    at.session_state["f_lender"] = "bank"
    at.run()
    at.slider(key="f_tenure").set_value(30).run()
    assert {m.label: m.value for m in at.metric}["Bank loan"] == "$198,000"  # 55% x 360,000


def test_borrow_less(no_key):
    at = start()
    at.toggle(key="f_borrow_max").set_value(False).run()
    at.slider(key="f_borrow").set_value(200000).run()
    assert {m.label: m.value for m in at.metric}["HDB loan"] == "$200,000"


def test_comparison_tab_shows_both_lenders(no_key):
    at = start()
    frames = [d for d in at.dataframe if "🏦 Bank loan" in d.value.columns]
    assert frames and len(frames[0].value) == 10
