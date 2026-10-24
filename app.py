"""Streamlit UI: a free form mode (no API key) and an optional chat mode, both feeding the same breakdown.

Run:  streamlit run app.py
"""
from __future__ import annotations

import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from agent import has_api_key, run_agent
from calculators import assess_household, get_project_price, policy

load_dotenv()  # local dev: reads ANTHROPIC_API_KEY from .env
if "ANTHROPIC_API_KEY" not in os.environ:
    try:  # Streamlit Cloud: reads it from the app's Secrets; raises if no secrets file exists
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:  # noqa: BLE001
        pass

st.set_page_config(page_title="BTO Affordability Agent", page_icon="🏠", layout="wide")

FORM_MODE = "Form (free)"
CHAT_MODE = "Chat with AI agent"
CUSTOM_PRICE = "Custom price"

# Each example drives both modes: a chat prompt, and the same household as form values.
EXAMPLES = {
    "Couple, both 25, $8k combined": {
        "prompt": (
            "We're a couple, both Singapore citizens and first-timers, ages 25 and 26. "
            "I earn $4,500 and my partner earns $3,500 a month. Combined CPF OA is $45,000 and we have "
            "$50,000 in cash. Can we afford a 4-room BTO in Tengah? Keys in about 4 years, we save $2,000 a month."
        ),
        "form": dict(f_household="family", f_age1=25, f_inc1=4500, f_oa1=25000, f_age2=26, f_inc2=3500,
                     f_oa2=20000, f_cash=50000, f_monthly_savings=2000, f_years=4,
                     f_price_choice="Tengah Garden Avenue (name TBC) · 4-room · low"),
    },
    "One income, $4k": {
        "prompt": (
            "Married couple, ages 28 and 27, citizens, first-timers. Only I work, $4,000 a month. "
            "CPF OA $30,000, cash $20,000. 4-room in Tengah, keys in 4 years, we save $800 a month."
        ),
        "form": dict(f_household="family", f_age1=28, f_inc1=4000, f_oa1=30000, f_age2=27, f_inc2=0,
                     f_oa2=0, f_cash=20000, f_monthly_savings=800, f_years=4,
                     f_price_choice="Tengah Garden Avenue (name TBC) · 4-room · low"),
    },
    "Single, 36, $4k": {
        "prompt": (
            "I'm single, 36, citizen, first-timer, earning $4,000 a month. CPF OA $60,000, cash $30,000. "
            "Can I afford a BTO priced around $250,000? Keys in 3 years."
        ),
        "form": dict(f_household="single", f_age1=36, f_inc1=4000, f_oa1=60000, f_cash=30000,
                     f_monthly_savings=0, f_years=3, f_price_choice=CUSTOM_PRICE, f_custom_price=250000,
                     f_flat_type="2-room"),
    },
}


def price_options() -> dict[str, tuple[str, str, str] | None]:
    """Label -> (project_id, flat_type, point) for every known project price, plus a custom price."""
    opts: dict[str, tuple[str, str, str] | None] = {}
    for pid, p in policy.node("projects").items():
        for flat_type in p["prices"]:
            for point in ("low", "high"):
                opts[f"{p['name']} · {flat_type} · {point}"] = (pid, flat_type, point)
    opts[CUSTOM_PRICE] = None
    return opts


FLAT_TYPES = list(policy.node("upfront", "option_fee", "by_flat_type"))
FORM_DEFAULTS = dict(f_household="family", f_age1=28, f_inc1=0, f_oa1=0, f_age2=28, f_inc2=0, f_oa2=0,
                     f_cash=0, f_monthly_savings=0, f_years=4, f_price_choice=next(iter(price_options())),
                     f_custom_price=300000, f_flat_type="4-room", f_citizens=True, f_first=True)

# ---------- state ----------
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []      # what the model sees (includes tool calls)
    st.session_state.chat = []              # what the user sees
    st.session_state.tool_log = []
    st.session_state.assessment = None
for k, v in FORM_DEFAULTS.items():
    st.session_state.setdefault(k, v)

key_available = has_api_key()

# ---------- sidebar ----------
with st.sidebar:
    mode = st.radio("Mode", [FORM_MODE, CHAT_MODE], index=0, disabled=not key_available, key="mode")
    if not key_available:
        st.caption("Chat mode needs an Anthropic API key (paid). Form mode runs the same calculators for free.")
    st.header("Try an example")
    for label, ex in EXAMPLES.items():
        if st.button(label, width="stretch"):
            if mode == CHAT_MODE:
                st.session_state.pending_prompt = ex["prompt"]
            else:
                st.session_state.update(FORM_DEFAULTS | ex["form"])
                st.session_state.run_form = True
    st.divider()
    st.caption(f"Policy as of **{policy.as_of()}**")
    st.caption("Income ceiling (families): $16,000 · EHG up to $120,000 · HDB loan 2.6%, 75% LTV, 30% MSR")
    if policy.is_stale():
        st.warning("Policy values may be out of date. Check hdb.gov.sg.")
    if st.button("Start over", width="stretch"):
        for k in ("api_messages", "chat", "tool_log", "assessment", *FORM_DEFAULTS):
            st.session_state.pop(k, None)
        st.rerun()

st.title("🏠 Can we afford a BTO?")
st.caption("Checks BTO affordability with 2026 HDB and CPF rules. Every number comes from "
           "tested Python calculators, not the AI. Estimate only; not financial advice.")

left, right = st.columns([3, 2], gap="large")


def _money(x: float) -> str:
    return f"${x:,.0f}"


# ---------- right panel: breakdown ----------
def render_breakdown(a: dict | None) -> None:
    with right:
        st.subheader("Your numbers")
        if not a:
            st.info("Fill in the form or pick an example. The breakdown appears here.")
            return

        verdict = a["cash"]["verdict"]
        colour = {"affordable": "green", "tight": "orange", "gap": "red", "ineligible": "red"}[verdict]
        st.markdown(f"### Verdict: :{colour}[{verdict.upper()}]")

        c1, c2, c3 = st.columns(3)
        c1.metric("Grant (EHG)", _money(a["grant"]["grant"]))
        c2.metric("HDB loan", _money(a["loan"]["loan"]))
        c3.metric("Monthly instalment", _money(a["loan"]["monthly_instalment"]))

        cash = a["cash"]
        price = a["inputs"]["flat_price"]
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "total", "relative", "total"],
            x=["Flat price", "Grant", "HDB loan", "CPF OA", "Cash for downpayment", "Upfront costs",
               "Total cash needed"],
            y=[price, -a["grant"]["grant"], -a["loan"]["loan"], -cash["from_cpf_oa"], 0,
               cash["upfront_costs"], 0],
            text=[_money(price), f"-{_money(a['grant']['grant'])}", f"-{_money(a['loan']['loan'])}",
                  f"-{_money(cash['from_cpf_oa'])}", _money(cash["cash_for_downpayment"]),
                  f"+{_money(cash['upfront_costs'])}", _money(cash["total_cash_needed"])],
            textposition="outside",
            connector={"line": {"width": 1}},
        ))
        fig.update_layout(title="Where the money comes from", height=360, margin=dict(t=50, b=10, l=10, r=10),
                          yaxis_title="SGD", showlegend=False)
        st.plotly_chart(fig, width="stretch")

        if cash["gap"] > 0:
            months = a.get("months_to_close_gap")
            extra = f" About {months} months of saving closes it." if months else ""
            st.error(f"Cash gap: {_money(cash['gap'])} (you have {_money(cash['cash_savings'])}).{extra}")
        else:
            st.success(f"Cash left after buying: {_money(cash['cash_left_after'])} "
                       f"(buffer target {_money(cash['cash_buffer_target'])}).")

        msr_pct = a["loan"].get("msr_used_pct")
        if msr_pct is not None:
            bar = go.Figure(go.Bar(x=[msr_pct], y=["Instalment"], orientation="h",
                                   text=[f"{msr_pct:.1f}% of income"], textposition="inside"))
            bar.add_vline(x=policy.value("hdb_loan", "msr") * 100, line_dash="dash",
                          annotation_text="30% MSR limit")
            bar.update_layout(height=140, margin=dict(t=10, b=10, l=10, r=10), xaxis=dict(range=[0, 40]),
                              xaxis_title="% of gross monthly income")
            st.plotly_chart(bar, width="stretch")
            st.caption(f"Loan limited by: **{a['loan']['binding_limit_label']}** · "
                       f"tenure {a['loan']['tenure_years']} years")

        for note in a["eligibility"].get("notes", []):
            st.info(note)
        with st.expander("Assumptions"):
            for item in a["assumptions"]:
                st.markdown(f"- {item}")
        if a["warnings"]:
            with st.expander(f"Warnings ({len(a['warnings'])})"):
                for w in a["warnings"]:
                    st.markdown(f"- {w}")
        st.caption(a["disclaimer"])


# ---------- left panel: form mode ----------
def assess_from_form() -> dict:
    s = st.session_state
    applicants = [1] if s.f_household == "single" else [1, 2]
    choice = price_options()[s.f_price_choice]
    if choice is None:
        flat_price, flat_type = s.f_custom_price, s.f_flat_type
    else:
        pid, flat_type, point = choice
        flat_price = get_project_price(pid, flat_type, point)["price_used"]
    return assess_household(
        household_type=s.f_household,
        incomes=[s[f"f_inc{i}"] for i in applicants],
        ages=[s[f"f_age{i}"] for i in applicants],
        cpf_oa_balances=[s[f"f_oa{i}"] for i in applicants],
        cash_savings=s.f_cash,
        flat_price=flat_price,
        flat_type=flat_type,
        years_until_key_collection=s.f_years,
        monthly_savings=s.f_monthly_savings,
        all_singapore_citizens=s.f_citizens,
        first_timers=s.f_first,
    )


def render_form() -> None:
    with left:
        st.subheader("Your household")
        st.radio("Applying as", ["family", "single"], horizontal=True, key="f_household",
                 format_func=lambda x: "Couple / family" if x == "family" else "Single (35+)")
        applicants = [1] if st.session_state.f_household == "single" else [1, 2]
        with st.form("household"):
            cols = st.columns(len(applicants))
            for col, i in zip(cols, applicants):
                with col:
                    st.markdown(f"**Applicant {i}**")
                    st.number_input("Age", min_value=21, max_value=80, step=1, key=f"f_age{i}")
                    st.number_input("Gross monthly income ($)", min_value=0, step=100, key=f"f_inc{i}")
                    st.number_input("CPF OA balance ($)", min_value=0, step=1000, key=f"f_oa{i}")
            st.markdown("**Savings and timing**")
            c1, c2, c3 = st.columns(3)
            c1.number_input("Cash savings ($)", min_value=0, step=1000, key="f_cash")
            c2.number_input("Monthly savings ($)", min_value=0, step=100, key="f_monthly_savings")
            c3.number_input("Years until keys", min_value=0, max_value=10, step=1, key="f_years")
            st.markdown("**Flat**")
            st.selectbox("Project and price", list(price_options()), key="f_price_choice",
                         help="Indicative prices before grants. Final prices only at launch.")
            c4, c5 = st.columns(2)
            c4.number_input("Custom price ($)", min_value=0, step=5000, key="f_custom_price",
                            help="Used only when 'Custom price' is selected.")
            c5.selectbox("Flat type (custom price)", FLAT_TYPES, key="f_flat_type")
            c6, c7 = st.columns(2)
            c6.checkbox("All applicants are Singapore citizens", key="f_citizens")
            c7.checkbox("First-time buyers", key="f_first")
            submitted = st.form_submit_button("Check affordability", type="primary", width="stretch")
        if submitted or st.session_state.pop("run_form", False):
            st.session_state.assessment = assess_from_form()


# ---------- left panel: chat mode ----------
def render_chat() -> None:
    with left:
        for role, text in st.session_state.chat:
            with st.chat_message(role):
                st.markdown(text)

        prompt = st.chat_input("e.g. Can we afford a 4-room in Tengah? We're 26 and earn $7k together...")
        prompt = prompt or st.session_state.pop("pending_prompt", None)

        if prompt:
            st.session_state.chat.append(("user", prompt))
            with st.chat_message("user"):
                st.markdown(prompt)
            n_before = len(st.session_state.api_messages)
            st.session_state.api_messages.append({"role": "user", "content": prompt})

            with st.chat_message("assistant"):
                with st.spinner("Running the numbers..."):
                    try:
                        turn = run_agent(st.session_state.api_messages)
                    except Exception as e:  # noqa: BLE001
                        turn = None
                        del st.session_state.api_messages[n_before:]  # roll back this turn so the next one is clean
                        st.session_state.chat.pop()
                        st.error(f"Agent error: {e}. Check ANTHROPIC_API_KEY.")
                if turn:
                    st.markdown(turn.text)
                    st.session_state.chat.append(("assistant", turn.text))
                    st.session_state.tool_log.extend(turn.tool_calls)
                    if turn.last_assessment:
                        st.session_state.assessment = turn.last_assessment

        if st.session_state.tool_log:
            with st.expander(f"🔧 Agent tool calls ({len(st.session_state.tool_log)})"):
                for i, c in enumerate(st.session_state.tool_log, 1):
                    st.markdown(f"**{i}. `{c.name}`**" + (" ⚠️ error" if c.is_error else ""))
                    st.json({"input": c.input, "output": c.output}, expanded=False)


if key_available and mode == CHAT_MODE:
    render_chat()
else:
    render_form()

render_breakdown(st.session_state.assessment)
