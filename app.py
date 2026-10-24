"""Streamlit UI: live calculator (free, no API key) and an optional chat mode, both feeding the same results.

Run:  streamlit run app.py
"""
from __future__ import annotations

import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from agent import has_api_key, run_agent
from calculators import assess_household, get_ehg_grant, get_project_price, policy
from calculators.assess import EMERGENCY_BUFFER_MONTHS

load_dotenv()  # local dev: reads ANTHROPIC_API_KEY from .env
if "ANTHROPIC_API_KEY" not in os.environ:
    try:  # Streamlit Cloud: reads it from the app's Secrets; raises if no secrets file exists
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:  # noqa: BLE001
        pass

st.set_page_config(page_title="BTO Affordability Agent", page_icon="🏠", layout="wide")

FORM_MODE = "Calculator (free)"
CHAT_MODE = "Chat with AI agent"
CUSTOM_PRICE = "Custom price"

# Chart colours: categorical slots from the dataviz reference palette; status colours are reserved for the verdict.
BLUE, AQUA, ORANGE, MUTED = "#2a78d6", "#1baf7a", "#eb6834", "#898781"
VERDICTS = {
    "affordable": ("✅", "Affordable", "#0a7d32", "#0ca30c", "#ffffff"),
    "tight": ("⚠️", "Tight", "#c98500", "#fab219", "#0b0b0b"),
    "gap": ("⛔", "Cash gap", "#a32626", "#d03b3b", "#ffffff"),
    "ineligible": ("🚫", "Not eligible", "#5c5b57", "#898781", "#ffffff"),
}


def price_options() -> dict[str, tuple[str, str, str] | None]:
    """Label -> (project_id, flat_type, point) for every known project price, plus a custom price."""
    opts: dict[str, tuple[str, str, str] | None] = {}
    for pid, p in policy.node("projects").items():
        for flat_type in p["prices"]:
            for point in ("low", "high"):
                opts[f"{p['town']} {flat_type} · {point}"] = (pid, flat_type, point)
    opts[CUSTOM_PRICE] = None
    return opts


FIRST_PROJECT_PRICE = next(iter(price_options()))
FLAT_TYPES = list(policy.node("upfront", "option_fee", "by_flat_type"))

# Each example drives both modes: a chat prompt, and the same household as calculator values.
EXAMPLES = {
    "👫  Couple, 25 & 26 · $8k": {
        "prompt": (
            "We're a couple, both Singapore citizens and first-timers, ages 25 and 26. "
            "I earn $4,500 and my partner earns $3,500 a month. Combined CPF OA is $45,000 and we have "
            "$50,000 in cash. Can we afford a 4-room BTO in Tengah? Keys in about 4 years, we save $2,000 a month."
        ),
        "form": dict(f_household="family", f_age1=25, f_inc1=4500, f_oa1=25000, f_age2=26, f_inc2=3500,
                     f_oa2=20000, f_cash=50000, f_monthly_savings=2000, f_years=4,
                     f_price_choice=FIRST_PROJECT_PRICE),
    },
    "💼  One income · $4k": {
        "prompt": (
            "Married couple, ages 28 and 27, citizens, first-timers. Only I work, $4,000 a month. "
            "CPF OA $30,000, cash $20,000. 4-room in Tengah, keys in 4 years, we save $800 a month."
        ),
        "form": dict(f_household="family", f_age1=28, f_inc1=4000, f_oa1=30000, f_age2=27, f_inc2=0,
                     f_oa2=0, f_cash=20000, f_monthly_savings=800, f_years=4,
                     f_price_choice=FIRST_PROJECT_PRICE),
    },
    "🧑  Single, 36 · $4k": {
        "prompt": (
            "I'm single, 36, citizen, first-timer, earning $4,000 a month. CPF OA $60,000, cash $30,000. "
            "Can I afford a BTO priced around $250,000? Keys in 3 years."
        ),
        "form": dict(f_household="single", f_age1=36, f_inc1=4000, f_oa1=60000, f_cash=30000,
                     f_monthly_savings=0, f_years=3, f_price_choice=CUSTOM_PRICE, f_custom_price=250000,
                     f_flat_type="2-room"),
    },
}

BASE_FORM = dict(f_household="family", f_age1=28, f_inc1=0, f_oa1=0, f_age2=28, f_inc2=0, f_oa2=0,
                 f_cash=0, f_monthly_savings=0, f_years=4, f_price_choice=FIRST_PROJECT_PRICE,
                 f_custom_price=300000, f_flat_type="4-room", f_citizens=True, f_first=True)
FORM_DEFAULTS = BASE_FORM | next(iter(EXAMPLES.values()))["form"]  # open on a filled-in example, not zeros

CSS = """
<style>
.hero {background: linear-gradient(120deg, #0d366b 0%, #1c5cab 45%, #2a78d6 75%, #1baf7a 120%);
       border-radius: 1.25rem; padding: 2rem 2.25rem 1.6rem; color: #fff; margin-bottom: 1.25rem;
       box-shadow: 0 12px 32px rgba(13, 54, 107, .25); position: relative; overflow: hidden;}
.hero::after {content: "🏠"; position: absolute; right: 1.5rem; top: .6rem; font-size: 7rem; opacity: .14;}
.hero h1 {color: #fff; margin: 0 0 .35rem; font-size: 2.4rem; line-height: 1.1; padding: 0;}
.hero p {color: rgba(255,255,255,.88); margin: 0 0 1rem; font-size: 1.05rem; max-width: 46rem;}
.chip {display: inline-block; background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.28);
       border-radius: 999px; padding: .22rem .75rem; margin: 0 .4rem .4rem 0; font-size: .82rem;
       color: #fff; backdrop-filter: blur(4px);}
.verdict {border-radius: 1.1rem; padding: 1.25rem 1.5rem; margin-bottom: 1rem;
          box-shadow: 0 8px 24px rgba(0,0,0,.12);}
.verdict .label {font-size: .8rem; letter-spacing: .08em; text-transform: uppercase; opacity: .85;}
.verdict .big {font-size: 2.1rem; font-weight: 800; line-height: 1.15; margin: .1rem 0 .35rem;}
.verdict .why {font-size: 1rem; opacity: .95;}
.step {font-weight: 700; font-size: 1.05rem; margin: .1rem 0 .4rem;}
.step span {display: inline-flex; align-items: center; justify-content: center; width: 1.6rem; height: 1.6rem;
            border-radius: 999px; background: #2a78d6; color: #fff; font-size: .85rem; margin-right: .5rem;}
.foot {opacity: .7; font-size: .85rem; text-align: center; margin-top: 2rem;}
</style>
"""

# ---------- state ----------
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []      # what the model sees (includes tool calls)
    st.session_state.chat = []              # what the user sees
    st.session_state.tool_log = []
    st.session_state.assessment = None
for k, v in FORM_DEFAULTS.items():
    st.session_state.setdefault(k, v)

key_available = has_api_key()


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _md(text: str) -> str:
    """Escape dollar signs: Streamlit markdown renders text between two $ as LaTeX."""
    return text.replace("$", r"\$")


def load_example(label: str) -> None:
    if st.session_state.get("mode") == CHAT_MODE:
        st.session_state.pending_prompt = EXAMPLES[label]["prompt"]
    else:
        st.session_state.update(BASE_FORM | EXAMPLES[label]["form"])


def start_over() -> None:
    for k in ("api_messages", "chat", "tool_log", "assessment", *FORM_DEFAULTS):
        st.session_state.pop(k, None)


# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### ⚙️ Mode")
    mode = st.radio("Mode", [FORM_MODE, CHAT_MODE], index=0, disabled=not key_available, key="mode",
                    label_visibility="collapsed")
    if not key_available:
        st.caption("💡 Chat mode needs an Anthropic API key (paid). The calculator runs the same tested "
                   "maths for free.")
    st.divider()
    st.markdown("### 📜 Policy snapshot")
    st.caption(f"As of **{policy.as_of()}**")
    st.markdown(_md(
        f"- Income ceiling (families): **{_money(policy.value('income_ceilings', 'family'))}**/month\n"
        f"- EHG grant: up to **{_money(policy.node('ehg', 'family')['bands'][0]['grant'])}**\n"
        f"- HDB loan: **{policy.value('hdb_loan', 'interest_rate'):.1%}** · "
        f"LTV **{policy.value('hdb_loan', 'ltv'):.0%}** · MSR **{policy.value('hdb_loan', 'msr'):.0%}**"
    ))
    if policy.is_stale():
        st.warning("Policy values may be out of date. Check hdb.gov.sg.")

st.html(CSS)
st.markdown(
    f"""<div class="hero">
      <h1>Can we afford a BTO?</h1>
      <p>Move the sliders and watch the grant, HDB loan and cash needed update instantly,
         using 2026 HDB and CPF rules.</p>
      <span class="chip">📅 Policy as of {policy.as_of()}</span>
      <span class="chip">🧮 Every number from tested Python, not AI</span>
      <span class="chip">🔗 Every rule linked to its source</span>
      <span class="chip">🆓 Free, no sign-up</span>
    </div>""",
    unsafe_allow_html=True,
)

ex_cols = st.columns([1, 1, 1, 0.7])
for col, label in zip(ex_cols, EXAMPLES):
    col.button(label, on_click=load_example, args=(label,), width="stretch")
ex_cols[-1].button("↺  Start over", on_click=start_over, width="stretch", type="tertiary")

left, right = st.columns([5, 7], gap="large")


# ---------- charts ----------
def _style(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, sans-serif", size=13), hoverlabel=dict(font_size=13))
    fig.update_yaxes(gridcolor="rgba(137,135,129,.25)", zeroline=False)
    fig.update_xaxes(showgrid=False)
    return fig


def waterfall_chart(a: dict) -> go.Figure:
    cash, price, grant, loan = a["cash"], a["inputs"]["flat_price"], a["grant"]["grant"], a["loan"]["loan"]
    labels = ["Flat price", "Grant", "HDB loan", "CPF OA", "Cash for<br>downpayment", "Upfront<br>costs",
              "Total cash<br>needed"]
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total", "relative", "total"],
        x=labels,
        y=[price, -grant, -loan, -cash["from_cpf_oa"], 0, cash["upfront_costs"], 0],
        text=[_money(price), f"−{_money(grant)}", f"−{_money(loan)}", f"−{_money(cash['from_cpf_oa'])}",
              _money(cash["cash_for_downpayment"]), f"+{_money(cash['upfront_costs'])}",
              _money(cash["total_cash_needed"])],
        textposition="outside",
        hovertemplate="%{x}: %{text}<extra></extra>",
        decreasing={"marker": {"color": AQUA}},
        increasing={"marker": {"color": ORANGE}},
        totals={"marker": {"color": BLUE}},
        connector={"line": {"width": 1, "color": MUTED, "dash": "dot"}},
    ))
    fig.update_yaxes(tickprefix="$", tickformat="~s", title=None)
    return _style(fig, 380)


def msr_gauge(a: dict) -> go.Figure:
    msr_pct = policy.value("hdb_loan", "msr") * 100
    used = a["loan"]["msr_used_pct"] or 0
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=used,
        number={"suffix": "%", "font": {"size": 44}},
        title={"text": "of gross monthly income goes to the loan", "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, msr_pct + 10], "ticksuffix": "%"},
            "bar": {"color": BLUE, "thickness": 0.35},
            "steps": [{"range": [0, msr_pct], "color": "rgba(42,120,214,.12)"},
                      {"range": [msr_pct, msr_pct + 10], "color": "rgba(208,59,59,.12)"}],
            "threshold": {"line": {"color": "#d03b3b", "width": 3}, "thickness": 0.9, "value": msr_pct},
        },
    ))
    return _style(fig, 260)


def grant_ladder(a: dict) -> go.Figure:
    household = a["inputs"]["household_type"]
    ceiling = policy.node("ehg", household)["income_ceiling"]
    step = 50
    incomes = list(range(0, int(ceiling * 1.25) + step, step))
    grants = [get_ehg_grant(household, x)["grant"] for x in incomes]
    you_income, you_grant = a["inputs"]["monthly_household_income"], a["grant"]["grant"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=incomes, y=grants, mode="lines", line=dict(color=BLUE, width=2, shape="hv"),
                             fill="tozeroy", fillcolor="rgba(42,120,214,.10)",
                             hovertemplate="Income $%{x:,}/month → grant $%{y:,}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[min(you_income, incomes[-1])], y=[you_grant], mode="markers+text",
                             marker=dict(size=14, color=ORANGE, line=dict(color="#ffffff", width=2)),
                             text=[f"You: {_money(you_grant)}"], textposition="top right",
                             hovertemplate="Your income $%{x:,} → grant $%{y:,}<extra></extra>"))
    fig.add_vline(x=ceiling, line_dash="dot", line_color=MUTED,
                  annotation_text=f"EHG ceiling {_money(ceiling)}", annotation_position="top left")
    fig.update_xaxes(title="Average gross monthly household income", tickprefix="$", tickformat=",")
    fig.update_yaxes(title=None, tickprefix="$", tickformat="~s")
    return _style(fig, 320)


def upfront_chart(a: dict) -> go.Figure:
    u = a["upfront"]
    verified = {i["rule"]: i["verified"] for i in policy.sourced_items()}
    rows = [("Option fee", u["option_fee"], "upfront.option_fee"),
            ("Buyer's stamp duty", u["buyer_stamp_duty"], "upfront.buyer_stamp_duty"),
            ("Mortgage stamp duty", u["mortgage_stamp_duty"], "upfront.mortgage_stamp_duty"),
            ("Application fee", u["application_fee"], "upfront.application_fee"),
            ("Legal & misc (estimate)", u["legal_and_misc_estimate"], "upfront.legal_and_misc_estimate")]
    rows.sort(key=lambda r: r[1])
    fig = go.Figure(go.Bar(
        x=[r[1] for r in rows],
        y=[r[0] + ("" if verified.get(r[2]) else "  ⚠️") for r in rows],
        orientation="h",
        marker=dict(color=[ORANGE if verified.get(r[2]) else "rgba(235,104,52,.30)" for r in rows],
                    pattern=dict(shape=["" if verified.get(r[2]) else "/" for r in rows],
                                 fgcolor=ORANGE, solidity=0.4)),
        text=[_money(r[1]) for r in rows], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    fig.update_xaxes(visible=False, range=[0, max(r[1] for r in rows) * 1.2])
    return _style(fig, 260)


# ---------- right panel: results ----------
def verdict_reason(a: dict) -> str:
    cash, verdict = a["cash"], a["cash"]["verdict"]
    if verdict == "ineligible":
        return " ".join(a["eligibility"]["reasons"]) or "This household does not meet the eligibility rules."
    if verdict == "gap":
        months = a.get("months_to_close_gap")
        extra = f" At your saving rate that's about {months} months." if months else ""
        return f"You'd be {_money(cash['gap'])} short in cash.{extra}"
    if verdict == "tight":
        return (f"You can pay, but you'd keep only {_money(cash['cash_left_after'])} in cash, below "
                f"{EMERGENCY_BUFFER_MONTHS} months of instalments ({_money(cash['cash_buffer_target'])}).")
    return (f"You'd still have {_money(cash['cash_left_after'])} in cash after buying, above "
            f"{EMERGENCY_BUFFER_MONTHS} months of instalments ({_money(cash['cash_buffer_target'])}).")


def render_results(a: dict | None) -> None:
    with right:
        if not a:
            st.info("👋 Tell the agent about your household, or pick an example above. "
                    "Your numbers appear here.")
            return

        icon, label, c1, c2, ink = VERDICTS[a["cash"]["verdict"]]
        st.markdown(
            f"""<div class="verdict" style="background: linear-gradient(120deg, {c1}, {c2}); color: {ink};">
                  <div class="label">Verdict · {_money(a['inputs']['flat_price'])} {a['inputs']['flat_type']}</div>
                  <div class="big">{icon} {label}</div>
                  <div class="why">{verdict_reason(a)}</div>
                </div>""",
            unsafe_allow_html=True,
        )

        cash, loan = a["cash"], a["loan"]
        row1, row2 = st.columns(2), st.columns(2)
        m1, m2, m3, m4 = *row1, *row2
        m1.metric("Grant (EHG)", _money(a["grant"]["grant"]), border=True, help=_md(a["grant"]["explanation"]))
        m2.metric("HDB loan", _money(loan["loan"]), border=True,
                  help=f"Limited by the {loan['binding_limit_label']}.")
        m3.metric("Monthly instalment", _money(loan["monthly_instalment"]), border=True,
                  delta=f"{loan['msr_used_pct']:.1f}% of income" if loan["msr_used_pct"] is not None else None,
                  delta_color="off", delta_arrow="off",
                  help=f"{loan['tenure_years']}-year tenure at {loan['interest_rate']:.1%}.")
        if cash["gap"] > 0:
            m4.metric("Cash gap", _money(cash["gap"]), border=True, delta="short of the cash needed",
                      delta_color="red", delta_arrow="off")
        else:
            m4.metric("Cash left after buying", _money(cash["cash_left_after"]), border=True)

        t1, t2, t3, t4, t5 = st.tabs(["💸 Money flow", "📅 Monthly", "🎁 Grant ladder", "🧾 Upfront",
                                      "📋 Assumptions & sources"])
        with t1:
            st.plotly_chart(waterfall_chart(a), width="stretch", config={"displayModeBar": False})
            st.caption(f"Flat price minus the grant and HDB loan is the downpayment. CPF OA pays first, then cash. "
                       f"Loan limited by: **{loan['binding_limit_label']}**.")
        with t2:
            if loan["msr_used_pct"] is None:
                st.info("No HDB loan: this household isn't eligible.")
            else:
                st.plotly_chart(msr_gauge(a), width="stretch", config={"displayModeBar": False})
                g1, g2, g3 = st.columns(3)
                g1.metric("Tenure", f"{loan['tenure_years']} years")
                g2.metric("Rate charged", f"{loan['interest_rate']:.1%}")
                g3.metric("Loan sized at", f"{loan['assessment_rate']:.1%}",
                          help="HDB sizes the loan at its interest rate floor, so the real instalment "
                               f"lands a little under the {policy.value('hdb_loan', 'msr'):.0%} cap.")
        with t3:
            st.plotly_chart(grant_ladder(a), width="stretch", config={"displayModeBar": False})
            st.caption(_md(f"{a['grant']['explanation']} Lower incomes get bigger grants; above the ceiling it's $0."))
        with t4:
            st.plotly_chart(upfront_chart(a), width="stretch", config={"displayModeBar": False})
            st.caption(_md(f"Total upfront: **{_money(a['upfront']['total'])}**. "
                           "⚠️ Faded, striped bars are placeholders still being verified."))
        with t5:
            for note in a["eligibility"].get("notes", []):
                st.info(_md(note))
            st.markdown("**Assumptions**")
            for item in a["assumptions"]:
                st.markdown(_md(f"- {item}"))
            if a["warnings"]:
                st.markdown("**Warnings**")
                for w in a["warnings"]:
                    st.warning(_md(w), icon="⚠️")
            st.markdown("**Where every rule comes from**")
            st.dataframe(
                [{"Rule": i["rule"], "Status": "✅ verified" if i["verified"] else "⚠️ to confirm",
                  "Source": i["source_url"]} for i in policy.sourced_items()],
                hide_index=True, width="stretch",
                column_config={"Source": st.column_config.LinkColumn(
                    display_text=r"https?://(?:www\.)?([^/]+)")},
            )


# ---------- left panel: calculator ----------
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


def _step(n: int, title: str) -> None:
    st.markdown(f'<div class="step"><span>{n}</span>{title}</div>', unsafe_allow_html=True)


def render_form() -> None:
    with left:
        with st.container(border=True):
            _step(1, "Who's applying?")
            st.segmented_control("Applying as", ["family", "single"], key="f_household", required=True,
                                 format_func=lambda x: "👫 Couple / family" if x == "family" else "🧑 Single (35+)",
                                 label_visibility="collapsed", width="stretch")
            applicants = [1] if st.session_state.f_household == "single" else [1, 2]
            cols = st.columns(len(applicants))
            for col, i in zip(cols, applicants):
                with col:
                    st.markdown(f"**{'You' if i == 1 else 'Partner'}**")
                    st.slider("Age", 21, 70, key=f"f_age{i}")
                    st.slider("Gross monthly income", 0, 20000, step=100, format="$%d", key=f"f_inc{i}")
                    st.slider("CPF OA balance", 0, 300000, step=1000, format="$%d", key=f"f_oa{i}")

        with st.container(border=True):
            _step(2, "Savings and timing")
            st.slider("Cash savings", 0, 300000, step=1000, format="$%d", key="f_cash")
            c1, c2 = st.columns(2)
            c1.slider("Saving each month", 0, 10000, step=100, format="$%d", key="f_monthly_savings")
            c2.slider("Years until keys", 0, 8, key="f_years")

        with st.container(border=True):
            _step(3, "Which flat?")
            st.segmented_control("Project and price", list(price_options()), key="f_price_choice",
                                 required=True, label_visibility="collapsed",
                                 help="Indicative prices before grants. Final prices only at launch.")
            if st.session_state.f_price_choice == CUSTOM_PRICE:
                c3, c4 = st.columns([2, 1])
                c3.slider("Flat price", 100000, 1000000, step=5000, format="$%d", key="f_custom_price")
                c4.selectbox("Flat type", FLAT_TYPES, key="f_flat_type")
            t1, t2 = st.columns(2)
            t1.toggle("All SG citizens", key="f_citizens")
            t2.toggle("First-time buyers", key="f_first")

    st.session_state.assessment = assess_from_form()


# ---------- left panel: chat mode ----------
def render_chat() -> None:
    with left:
        chat_box = st.container(height=560, border=True)
        with chat_box:
            if not st.session_state.chat:
                st.chat_message("assistant").markdown(
                    "Hi! Tell me your ages, incomes, CPF OA, cash savings and which flat you're eyeing, "
                    "and I'll run the numbers.")
            for role, text in st.session_state.chat:
                st.chat_message(role).markdown(text)

        prompt = st.chat_input("e.g. Can we afford a 4-room in Tengah? We're 26 and earn $7k together...")
        prompt = prompt or st.session_state.pop("pending_prompt", None)

        if prompt:
            st.session_state.chat.append(("user", prompt))
            with chat_box:
                st.chat_message("user").markdown(prompt)
            n_before = len(st.session_state.api_messages)
            st.session_state.api_messages.append({"role": "user", "content": prompt})

            with chat_box, st.chat_message("assistant"):
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

render_results(st.session_state.assessment)

st.markdown(f'<div class="foot">{policy.value("meta", "disclaimer")} · Policy as of {policy.as_of()}</div>',
            unsafe_allow_html=True)
