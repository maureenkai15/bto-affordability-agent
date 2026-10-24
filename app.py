"""Streamlit UI: chat on the left, live breakdown on the right.

Run:  streamlit run app.py
"""
from __future__ import annotations

import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from agent import run_agent
from calculators import policy

load_dotenv()  # local dev: reads ANTHROPIC_API_KEY from .env
if "ANTHROPIC_API_KEY" not in os.environ:
    try:  # Streamlit Cloud: reads it from the app's Secrets; raises if no secrets file exists
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:  # noqa: BLE001
        pass

st.set_page_config(page_title="BTO Affordability Agent", page_icon="🏠", layout="wide")

EXAMPLES = {
    "Couple, both 25, $8k combined": (
        "We're a couple, both Singapore citizens and first-timers, ages 25 and 26. "
        "I earn $4,500 and my partner earns $3,500 a month. Combined CPF OA is $45,000 and we have "
        "$50,000 in cash. Can we afford a 4-room BTO in Tengah? Keys in about 4 years, we save $2,000 a month."
    ),
    "One income, $4k": (
        "Married couple, ages 28 and 27, citizens, first-timers. Only I work, $4,000 a month. "
        "CPF OA $30,000, cash $20,000. 4-room in Tengah, keys in 4 years, we save $800 a month."
    ),
    "Single, 36, $4k": (
        "I'm single, 36, citizen, first-timer, earning $4,000 a month. CPF OA $60,000, cash $30,000. "
        "Can I afford a BTO priced around $250,000? Keys in 3 years."
    ),
}

# ---------- state ----------
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []      # what the model sees (includes tool calls)
    st.session_state.chat = []              # what the user sees
    st.session_state.tool_log = []
    st.session_state.assessment = None

# ---------- sidebar ----------
with st.sidebar:
    st.header("Try an example")
    for label, prompt in EXAMPLES.items():
        if st.button(label, width="stretch"):
            st.session_state.pending_prompt = prompt
    st.divider()
    st.caption(f"Policy as of **{policy.as_of()}**")
    st.caption("Income ceiling (families): $16,000 · EHG up to $120,000 · HDB loan 2.6%, 75% LTV, 30% MSR")
    if policy.is_stale():
        st.warning("Policy values may be out of date. Check hdb.gov.sg.")
    if st.button("Start over", width="stretch"):
        for k in ("api_messages", "chat", "tool_log", "assessment"):
            st.session_state.pop(k, None)
        st.rerun()

st.title("🏠 Can we afford a BTO?")
st.caption("An AI agent that checks BTO affordability with 2026 HDB and CPF rules. Every number comes from "
           "tested Python calculators, not the AI. Estimate only; not financial advice.")

left, right = st.columns([3, 2], gap="large")


def _money(x: float) -> str:
    return f"${x:,.0f}"


# ---------- right panel: breakdown ----------
def render_breakdown(a: dict | None) -> None:
    with right:
        st.subheader("Your numbers")
        if not a:
            st.info("Ask a question or pick an example. The breakdown appears here once the agent has your details.")
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
            bar.add_vline(x=30, line_dash="dash", annotation_text="30% MSR limit")
            bar.update_layout(height=140, margin=dict(t=10, b=10, l=10, r=10), xaxis=dict(range=[0, 40]),
                              xaxis_title="% of gross monthly income")
            st.plotly_chart(bar, width="stretch")
            st.caption(f"Loan limited by: **{a['loan']['binding_limit_label']}** · "
                       f"tenure {a['loan']['tenure_years']} years")

        with st.expander("Assumptions"):
            for item in a["assumptions"]:
                st.markdown(f"- {item}")
        if a["warnings"]:
            with st.expander(f"Warnings ({len(a['warnings'])})"):
                for w in a["warnings"]:
                    st.markdown(f"- {w}")


# ---------- left panel: chat ----------
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
        st.session_state.api_messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Running the numbers..."):
                try:
                    turn = run_agent(st.session_state.api_messages)
                except Exception as e:  # noqa: BLE001
                    turn = None
                    st.error(f"Agent error: {e}. Check ANTHROPIC_API_KEY in .env.")
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

render_breakdown(st.session_state.assessment)
