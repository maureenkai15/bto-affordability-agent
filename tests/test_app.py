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


def click_example(at, label):
    next(b for b in at.sidebar.button if b.label == label).click()
    at.run()
    assert not at.exception
    return at


@pytest.mark.parametrize("key, expected", [
    ("", False), ("sk-ant-...", False), ("not-a-key", False), ("sk-ant-api03-abc123", True),
])
def test_has_api_key(monkeypatch, key, expected):
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    assert has_api_key() is expected


def test_chat_mode_disabled_without_key(no_key):
    at = start()
    assert at.sidebar.radio[0].disabled
    assert at.sidebar.radio[0].value == "Form (free)"


def test_example_couple_hand_checked(no_key):
    at = click_example(start(), "Couple, both 25, $8k combined")
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Grant (EHG)"] == "$20,000"     # $7,501-$8,000 band
    assert metrics["HDB loan"] == "$270,000"       # 75% LTV of $360,000
    # cash left = 50,000 - (25,000 downpayment after CPF + 10,910 upfront)
    assert "Cash left after buying: $14,090" in at.success[0].value
    assert any("AFFORDABLE" in m.value for m in at.markdown)


def test_example_one_income_msr_binds(no_key):
    at = click_example(start(), "One income, $4k")
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Grant (EHG)"] == "$80,000"     # $3,501-$4,000 band
    assert metrics["HDB loan"] == "$253,052"           # 30% x $4,000 sized at the 3.0% floor
    assert metrics["Monthly instalment"] == "$1,148"   # same loan paid at 2.6%
    assert any(c.value.startswith("Loan limited by: **30% mortgage servicing ratio**") for c in at.caption)


def test_example_single_runs_and_warns(no_key):
    at = click_example(start(), "Single, 36, $4k")
    assert any("Verdict" in m.value for m in at.markdown)
    assert any(e.label.startswith("Warnings") for e in at.expander)


def test_start_over_clears(no_key):
    at = click_example(start(), "Couple, both 25, $8k combined")
    next(b for b in at.sidebar.button if b.label == "Start over").click()
    at.run()
    assert not at.metric
