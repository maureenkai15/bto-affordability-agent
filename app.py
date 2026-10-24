"""Streamlit UI: live calculator (free, no API key) and an optional chat mode, both feeding the same results.

Run:  streamlit run app.py
"""
from __future__ import annotations

import os

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from agent import has_api_key, run_agent
from calculators import (
    assess_household,
    get_ehg_grant,
    get_project_price,
    list_projects,
    monthly_instalment,
    policy,
)
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
CUSTOM = "custom"

# Chart colours: categorical slots from the dataviz reference palette; status colours are reserved for the verdict.
BLUE, ORANGE, AQUA, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#898781"
CLASS_COLOURS = {"Standard": BLUE, "Plus": ORANGE, "Prime": AQUA}
VERDICTS = {
    "affordable": ("✅", "Affordable", "#0a7d32", "#0ca30c", "#ffffff"),
    "tight": ("⚠️", "Tight", "#c98500", "#fab219", "#0b0b0b"),
    "gap": ("⛔", "Cash gap", "#a32626", "#d03b3b", "#ffffff"),
    "ineligible": ("🚫", "Not eligible", "#5c5b57", "#898781", "#ffffff"),
}
FLAT_LABELS = {"2-room": "2-room Flexi", "3-room": "3-room", "4-room": "4-room", "5-room": "5-room", "3gen": "3Gen"}
REGIONS = ["North", "North-East", "East", "West", "Central"]

PROJECTS = {p["project_id"]: p for p in list_projects()}
FLAT_TYPES = list(policy.node("upfront", "option_fee", "by_flat_type"))
BANK_RATE_DEFAULT = policy.value("bank_loan", "indicative_rate")

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
                     f_project="tengah-garden-avenue", f_flat_type="4-room", f_price=360000),
    },
    "💼  One income · $4k": {
        "prompt": (
            "Married couple, ages 28 and 27, citizens, first-timers. Only I work, $4,000 a month. "
            "CPF OA $30,000, cash $20,000. 4-room in Tengah, keys in 4 years, we save $800 a month."
        ),
        "form": dict(f_household="family", f_age1=28, f_inc1=4000, f_oa1=30000, f_age2=27, f_inc2=0,
                     f_oa2=0, f_cash=20000, f_monthly_savings=800, f_years=4,
                     f_project="tengah-garden-avenue", f_flat_type="4-room", f_price=360000),
    },
    "🧑  Single, 36 · $4k": {
        "prompt": (
            "I'm single, 36, citizen, first-timer, earning $4,000 a month. CPF OA $60,000, cash $30,000. "
            "Can I afford a BTO priced around $250,000? Keys in 3 years."
        ),
        "form": dict(f_household="single", f_age1=36, f_inc1=4000, f_oa1=60000, f_cash=30000,
                     f_monthly_savings=0, f_years=3, f_project=CUSTOM, f_custom_price=250000,
                     f_custom_type="2-room"),
    },
}

BASE_FORM = dict(f_household="family", f_age1=28, f_inc1=0, f_oa1=0, f_age2=28, f_inc2=0, f_oa2=0,
                 f_cash=0, f_monthly_savings=0, f_years=4, f_project="tengah-garden-avenue", f_flat_type="4-room",
                 f_price=360000, f_custom_price=300000, f_custom_type="4-room", f_citizens=True, f_first=True,
                 f_lender="hdb", f_bank_rate=round(BANK_RATE_DEFAULT * 100, 2), f_borrow_max=True,
                 f_regions=REGIONS, f_status="All")
FORM_DEFAULTS = BASE_FORM | next(iter(EXAMPLES.values()))["form"]  # open on a filled-in example, not zeros
RESETTABLE = ("f_tenure", "f_borrow")  # depend on other inputs; recomputed when cleared

CSS = """
<style>
@keyframes drift {0% {background-position: 0% 50%} 50% {background-position: 100% 50%} 100% {background-position: 0% 50%}}
@keyframes pop {0% {transform: scale(.6); opacity: 0} 70% {transform: scale(1.12)} 100% {transform: scale(1); opacity: 1}}
@keyframes rise {from {transform: translateY(8px); opacity: 0} to {transform: none; opacity: 1}}
.hero {background: linear-gradient(120deg, #0d366b, #1c5cab, #2a78d6, #1baf7a, #1c5cab);
       background-size: 300% 300%; animation: drift 18s ease infinite;
       border-radius: 1.5rem; padding: 2.2rem 2.4rem 1.7rem; color: #fff; margin-bottom: 1.4rem;
       box-shadow: 0 18px 40px rgba(13, 54, 107, .28); position: relative; overflow: hidden;}
.hero::before {content: ""; position: absolute; width: 420px; height: 420px; right: -120px; top: -180px;
       background: radial-gradient(circle, rgba(255,255,255,.22), transparent 65%); border-radius: 50%;}
.hero::after {content: "🏠"; position: absolute; right: 2rem; bottom: .4rem; font-size: 7.5rem; opacity: .16;}
.hero h1 {color: #fff; margin: 0 0 .4rem; font-size: 2.6rem; line-height: 1.08; padding: 0; letter-spacing: -.02em;}
.hero p {color: rgba(255,255,255,.9); margin: 0 0 1.2rem; font-size: 1.08rem; max-width: 46rem;}
.stats {display: flex; gap: 2.2rem; flex-wrap: wrap; margin-bottom: 1rem;}
.stats div {line-height: 1.1;}
.stats b {display: block; font-size: 1.9rem; font-weight: 800; color: #fff;}
.stats span {font-size: .8rem; letter-spacing: .06em; text-transform: uppercase; color: rgba(255,255,255,.75);}
.chip {display: inline-block; background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.3);
       border-radius: 999px; padding: .22rem .8rem; margin: 0 .4rem .4rem 0; font-size: .8rem; color: #fff;
       backdrop-filter: blur(6px);}
.section {font-size: 1.45rem; font-weight: 800; margin: 1.2rem 0 .2rem; letter-spacing: -.01em;}
.section small {display: block; font-size: .92rem; font-weight: 400; opacity: .65; margin-top: .15rem;}
.verdict {border-radius: 1.2rem; padding: 1.3rem 1.5rem; margin-bottom: 1rem; animation: rise .45s ease;
          box-shadow: 0 12px 30px rgba(0,0,0,.14); position: relative; overflow: hidden;}
.verdict::after {content: ""; position: absolute; width: 260px; height: 260px; right: -80px; top: -120px;
          background: radial-gradient(circle, rgba(255,255,255,.25), transparent 65%); border-radius: 50%;}
.verdict .label {font-size: .78rem; letter-spacing: .08em; text-transform: uppercase; opacity: .85;}
.verdict .big {font-size: 2.2rem; font-weight: 800; line-height: 1.15; margin: .15rem 0 .35rem;}
.verdict .big .icon {display: inline-block; animation: pop .5s ease;}
.verdict .why {font-size: 1rem; opacity: .95;}
.step {font-weight: 700; font-size: 1.05rem; margin: .1rem 0 .5rem;}
.step span {display: inline-flex; align-items: center; justify-content: center; width: 1.7rem; height: 1.7rem;
            border-radius: 999px; background: linear-gradient(135deg, #2a78d6, #1baf7a); color: #fff;
            font-size: .85rem; margin-right: .55rem; box-shadow: 0 4px 10px rgba(42,120,214,.35);}
.badge {display: inline-block; border-radius: 999px; padding: .15rem .65rem; font-size: .75rem; font-weight: 700;
        margin: 0 .3rem .3rem 0; color: #fff;}
.badge.soft {background: rgba(137,135,129,.18); color: inherit; font-weight: 600;}
.pcard h3 {margin: .1rem 0 .1rem; padding: 0; font-size: 1.35rem;}
.pcard .meta {opacity: .7; font-size: .9rem; margin-bottom: .5rem;}
.basis {font-size: .82rem; opacity: .75; border-left: 3px solid #eb6834; padding-left: .6rem; margin: .4rem 0;}
.timeline {display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin: .5rem 0 1rem;}
.tl {border-radius: 1rem; padding: .9rem 1rem; background: rgba(42,120,214,.08); border: 1px solid rgba(42,120,214,.18);
     position: relative; animation: rise .4s ease both;}
.tl:nth-child(2) {animation-delay: .06s} .tl:nth-child(3) {animation-delay: .12s} .tl:nth-child(4) {animation-delay: .18s}
.tl .n {font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; opacity: .65;}
.tl .t {font-weight: 700; margin: .15rem 0 .3rem;}
.tl .v {font-size: 1.35rem; font-weight: 800; color: #2a78d6;}
.tl .d {font-size: .8rem; opacity: .75; margin-top: .25rem;}
@media (max-width: 800px) {.hero h1 {font-size: 2rem;} .stats {gap: 1.2rem;}}
[class*="st-key-card"] {border-radius: 1.2rem !important; transition: box-shadow .2s ease, transform .2s ease;
       box-shadow: 0 2px 10px rgba(0,0,0,.04);}
[class*="st-key-card"]:hover {box-shadow: 0 10px 28px rgba(42,120,214,.14); transform: translateY(-2px);}
.legend {display: flex; flex-wrap: wrap; gap: .4rem 1.1rem; font-size: .8rem; opacity: .85; margin-top: -.3rem;}
.legend i {display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .35rem;
           vertical-align: -1px;}
.foot {opacity: .7; font-size: .85rem; text-align: center; margin-top: 2.4rem;}
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


def _class(p: dict) -> str:
    return p["classification"].split(" ")[0]


def _badge(text: str, colour: str | None = None) -> str:
    return (f'<span class="badge" style="background:{colour}">{text}</span>' if colour
            else f'<span class="badge soft">{text}</span>')


def load_example(label: str) -> None:
    if st.session_state.get("mode") == CHAT_MODE:
        st.session_state.pending_prompt = EXAMPLES[label]["prompt"]
    else:
        for k in RESETTABLE:
            st.session_state.pop(k, None)
        st.session_state.update(BASE_FORM | EXAMPLES[label]["form"])


def start_over() -> None:
    for k in ("api_messages", "chat", "tool_log", "assessment", *FORM_DEFAULTS, *RESETTABLE):
        st.session_state.pop(k, None)


def on_project_change() -> None:
    pid = st.session_state.f_project
    if pid != CUSTOM:
        types = PROJECTS[pid]["flat_types"]
        if st.session_state.f_flat_type not in types:
            st.session_state.f_flat_type = "4-room" if "4-room" in types else types[0]
        on_flat_type_change()


def on_flat_type_change() -> None:
    pid = st.session_state.f_project
    if pid != CUSTOM:
        st.session_state.f_price = get_project_price(pid, st.session_state.f_flat_type)["price_low"]
    st.session_state.pop("f_borrow", None)


def on_lender_change() -> None:
    for k in RESETTABLE:
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
        f"LTV **{policy.value('hdb_loan', 'ltv'):.0%}** · MSR **{policy.value('hdb_loan', 'msr'):.0%}**\n"
        f"- Bank loan: LTV **{policy.value('bank_loan', 'ltv'):.0%}**, stress-tested at "
        f"**{policy.value('bank_loan', 'assessment_rate_floor'):.0%}**"
    ))
    if policy.is_stale():
        st.warning("Policy values may be out of date. Check hdb.gov.sg.")

st.html(CSS)
verified = [i for i in policy.sourced_items() if i["verified"] and not i["rule"].startswith("projects.")]
rules = [i for i in policy.sourced_items() if not i["rule"].startswith("projects.")]
st.markdown(
    f"""<div class="hero">
      <h1>Can we afford a BTO?</h1>
      <p>Pick a project anywhere in Singapore, move the sliders, and watch the grant, loan, monthly instalment
         and cash needed update instantly, using 2026 HDB, CPF and MAS rules.</p>
      <div class="stats">
        <div><b>{len(PROJECTS)}</b><span>BTO projects</span></div>
        <div><b>{len({p['town'] for p in PROJECTS.values()})}</b><span>towns</span></div>
        <div><b>2</b><span>loan types</span></div>
        <div><b>{len(verified)}/{len(rules)}</b><span>rules verified</span></div>
      </div>
      <span class="chip">📅 Policy as of {policy.as_of()}</span>
      <span class="chip">🧮 Every number from tested Python, not AI</span>
      <span class="chip">🔗 Every rule linked to its source</span>
      <span class="chip">🆓 Free, no sign-up</span>
    </div>""",
    unsafe_allow_html=True,
)


# ---------- charts ----------
def _style(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, sans-serif", size=13), hoverlabel=dict(font_size=13))
    fig.update_yaxes(gridcolor="rgba(137,135,129,.25)", zeroline=False)
    fig.update_xaxes(showgrid=False)
    return fig


def project_map(visible: list[dict], selected: str) -> go.Figure:
    fig = go.Figure()
    for cls, colour in CLASS_COLOURS.items():
        for status, opacity in (("launched", 0.95), ("upcoming", 0.55)):
            pts = [p for p in visible if _class(p) == cls and p["status"] == status]
            if not pts:
                continue
            fig.add_trace(go.Scattermap(
                lat=[p["location"]["lat"] for p in pts], lon=[p["location"]["lon"] for p in pts],
                mode="markers", name=f"{cls} · {'upcoming' if status == 'upcoming' else 'launched'}",
                marker=dict(size=[11 + p["units"] / 160 for p in pts], color=colour, opacity=opacity),
                customdata=[[p["name"], p["town"], p["classification"], p["exercise"], f"{p['units']:,}"]
                            for p in pts],
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>"
                              "%{customdata[3]} · %{customdata[4]} flats<extra></extra>",
            ))
    if selected in PROJECTS:
        p = PROJECTS[selected]
        fig.add_trace(go.Scattermap(lat=[p["location"]["lat"]], lon=[p["location"]["lon"]], mode="markers+text",
                                    marker=dict(size=34, color="rgba(235,104,52,.28)"), text=[f"  {p['name']}"],
                                    textposition="middle right", textfont=dict(size=13, color="#eb6834"),
                                    hoverinfo="skip", showlegend=False))
    dark = getattr(getattr(st.context, "theme", None), "type", None) == "dark"
    fig.update_layout(map=dict(style="carto-darkmatter" if dark else "carto-positron",
                               center=dict(lat=1.352, lon=103.835), zoom=10.15),
                      height=430, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)",
                      showlegend=False)
    return fig


def map_legend() -> str:
    dots = "".join(f'<span><i style="background:{c}"></i>{name}</span>' for name, c in CLASS_COLOURS.items())
    return (f'<div class="legend">{dots}<span><i style="background:{MUTED};opacity:.45"></i>faded = upcoming</span>'
            f'<span>◯ size = number of flats · locations approximate</span></div>')


def price_dumbbell(pid: str, flat_type: str, price: float) -> go.Figure:
    p = PROJECTS[pid]
    rows = [(FLAT_LABELS.get(t, t), get_project_price(pid, t)) for t in p["flat_types"]]
    fig = go.Figure()
    for label, r in rows:
        fig.add_trace(go.Scatter(x=[r["price_low"], r["price_high"]], y=[label, label], mode="lines+markers",
                                 line=dict(color=BLUE, width=6), marker=dict(size=10, color=BLUE),
                                 hovertemplate=f"{label}: %{{x:$,.0f}}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[price], y=[FLAT_LABELS.get(flat_type, flat_type)], mode="markers",
                             marker=dict(size=16, color=ORANGE, symbol="diamond", line=dict(color="#fff", width=2)),
                             hovertemplate="Your price: %{x:$,.0f}<extra></extra>"))
    fig.update_xaxes(tickprefix="$", tickformat="~s", showgrid=True, gridcolor="rgba(137,135,129,.2)")
    return _style(fig, 60 + 42 * len(rows))


def waterfall_chart(a: dict) -> go.Figure:
    cash, price, grant, loan = a["cash"], a["inputs"]["flat_price"], a["grant"]["grant"], a["loan"]["loan"]
    labels = ["Flat price", "Grant", "Loan", "CPF OA", "Cash for<br>downpayment", "Upfront<br>costs",
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
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=a["loan"]["msr_used_pct"] or 0,
        number={"suffix": "%", "font": {"size": 42}},
        title={"text": "of income on the loan", "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, msr_pct + 10], "ticksuffix": "%"},
            "bar": {"color": BLUE, "thickness": 0.35},
            "steps": [{"range": [0, msr_pct], "color": "rgba(42,120,214,.12)"},
                      {"range": [msr_pct, msr_pct + 10], "color": "rgba(208,59,59,.12)"}],
            "threshold": {"line": {"color": "#d03b3b", "width": 3}, "thickness": 0.9, "value": msr_pct},
        },
    ))
    return _style(fig, 240)


def rate_curve(a: dict) -> go.Figure:
    """Monthly instalment on this loan across interest rates, with the HDB, bank and stress-test rates marked."""
    loan, tenure = a["loan"]["loan"], a["loan"]["tenure_years"]
    rates = [x / 1000 for x in range(10, 61, 1)]  # 1.0% to 6.0%
    fig = go.Figure(go.Scatter(x=[r * 100 for r in rates], y=[monthly_instalment(loan, r, tenure) for r in rates],
                               mode="lines", line=dict(color=BLUE, width=2.5),
                               hovertemplate="At %{x:.1f}%: %{y:$,.0f}/month<extra></extra>"))
    marks = [("HDB", policy.value("hdb_loan", "interest_rate"), BLUE),
             ("Your bank rate", st.session_state.get("f_bank_rate", BANK_RATE_DEFAULT * 100) / 100, ORANGE),
             ("MAS stress test", policy.value("bank_loan", "assessment_rate_floor"), MUTED)]
    for name, r, colour in marks:
        y = monthly_instalment(loan, r, tenure)
        fig.add_trace(go.Scatter(x=[r * 100], y=[y], mode="markers+text", text=[f"{name}<br>{_money(y)}"],
                                 textposition="bottom right" if name == "Your bank rate" else "top left",
                                 marker=dict(size=11, color=colour, line=dict(color="#fff", width=2)),
                                 hovertemplate=f"{name} %{{x:.2f}}%: %{{y:$,.0f}}/month<extra></extra>"))
    cap = a["loan"].get("msr_max_instalment")
    if cap:
        fig.add_hline(y=cap, line_dash="dot", line_color="#d03b3b",
                      annotation_text=f"{policy.value('hdb_loan', 'msr'):.0%} of income = {_money(cap)}",
                      annotation_position="top left")
    ys = [monthly_instalment(loan, r, tenure) for r in rates] + [cap or 0]
    fig.update_xaxes(title="Interest rate (% a year)", ticksuffix="%")
    fig.update_yaxes(title=None, tickprefix="$", tickformat=",", range=[min(ys) * 0.75, max(ys) * 1.08])
    return _style(fig, 340)


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
    verified_rules = {i["rule"]: i["verified"] for i in policy.sourced_items()}
    rows = [("Option fee", u["option_fee"], "upfront.option_fee"),
            ("Buyer's stamp duty", u["buyer_stamp_duty"], "upfront.buyer_stamp_duty"),
            ("Mortgage stamp duty", u["mortgage_stamp_duty"], "upfront.mortgage_stamp_duty"),
            ("Application fee", u["application_fee"], "upfront.application_fee"),
            ("Legal & misc (estimate)", u["legal_and_misc_estimate"], "upfront.legal_and_misc_estimate")]
    rows.sort(key=lambda r: r[1])
    fig = go.Figure(go.Bar(
        x=[r[1] for r in rows],
        y=[r[0] + ("" if verified_rules.get(r[2]) else "  ⚠️") for r in rows],
        orientation="h",
        marker=dict(color=[ORANGE if verified_rules.get(r[2]) else "rgba(235,104,52,.30)" for r in rows],
                    pattern=dict(shape=["" if verified_rules.get(r[2]) else "/" for r in rows],
                                 fgcolor=ORANGE, solidity=0.4)),
        text=[_money(r[1]) for r in rows], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    fig.update_xaxes(visible=False, range=[0, max(r[1] for r in rows) * 1.2])
    return _style(fig, 240)


def interest_bars(hdb: dict, bank: dict) -> go.Figure:
    names = [f"HDB loan<br>{hdb['loan']['interest_rate']:.2%}", f"Bank loan<br>{bank['loan']['interest_rate']:.2%}"]
    vals = [hdb["loan"]["total_interest"], bank["loan"]["total_interest"]]
    fig = go.Figure(go.Bar(x=names, y=vals, marker=dict(color=[BLUE, ORANGE]), width=0.45,
                           text=[_money(v) for v in vals], textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}: %{text} total interest<extra></extra>"))
    fig.update_yaxes(visible=False, range=[0, max(vals + [1]) * 1.25])
    fig.update_layout(title=dict(text="Total interest over the loan", font=dict(size=14)))
    return _style(fig, 270)


# ---------- explore projects ----------
def render_explorer() -> None:
    st.markdown('<div class="section">🗺️ Explore BTO projects across Singapore'
                '<small>Launched in 2026 with HDB prices, and the November 2026 exercise (prices at launch). '
                'Pick a project to test it below.</small></div>', unsafe_allow_html=True)
    f1, f2 = st.columns([3, 2])
    f1.pills("Regions", REGIONS, selection_mode="multi", key="f_regions", label_visibility="collapsed")
    f2.segmented_control("Status", ["All", "Upcoming", "Launched"], key="f_status", required=True,
                         label_visibility="collapsed", width="stretch")
    regions = st.session_state.f_regions or REGIONS
    status = st.session_state.f_status
    visible = [p for p in PROJECTS.values() if p["region"] in regions
               and (status == "All" or p["status"] == status.lower())]
    selected = st.session_state.f_project

    m, card = st.columns([3, 2], gap="large")
    with m, st.container(border=True, key="card-map"):
        st.plotly_chart(project_map(visible, selected), width="stretch", config={"displayModeBar": False,
                                                                                 "scrollZoom": False})
        st.markdown(map_legend(), unsafe_allow_html=True)
    with card, st.container(border=True, key="card-project"):
        options = [CUSTOM] + sorted((p["project_id"] for p in visible),
                                    key=lambda i: (PROJECTS[i]["status"] != "upcoming", PROJECTS[i]["town"]))
        if selected not in options:
            options.insert(1, selected)
        st.selectbox("Project", options, key="f_project", on_change=on_project_change,
                     format_func=lambda i: "✏️  My own price" if i == CUSTOM else
                     f"{'🆕' if PROJECTS[i]['status'] == 'upcoming' else '🏗️'}  {PROJECTS[i]['name']} · "
                     f"{PROJECTS[i]['town']}")
        if selected == CUSTOM:
            st.markdown("**Enter any price** below the map, in step ③.")
            return
        p = PROJECTS[selected]
        cls = _class(p)
        badges = _badge(p["classification"], CLASS_COLOURS[cls]) + _badge(p["exercise"]) + \
            _badge("Upcoming · prices at launch" if p["status"] == "upcoming" else "Launched")
        wait = f" · ~{p['waiting_time_months']} months to keys" if p.get("waiting_time_months") else ""
        st.markdown(f'<div class="pcard"><h3>{p["name"]}</h3><div class="meta">{p["town"]} · {p["region"]} · '
                    f'{p["units"]:,} flats{wait}</div>{badges}</div>', unsafe_allow_html=True)
        r = get_project_price(selected, st.session_state.f_flat_type)
        if "error" not in r and p["status"] == "upcoming":
            st.markdown(f'<div class="basis">Prices: {r["price_basis"]}.</div>', unsafe_allow_html=True)
        st.plotly_chart(price_dumbbell(selected, st.session_state.f_flat_type, st.session_state.f_price),
                        width="stretch", config={"displayModeBar": False})
        st.caption("Indicative price ranges before grants. ◆ = the price you're testing.")


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


def render_timeline(a: dict) -> None:
    s, loan = a["stages"], a["loan"]
    steps = [
        ("1 · Booking", "Option fee", _money(s["booking_option_fee"]), "Paid when you pick your flat."),
        ("2 · Signing", f"Downpayment {s['signing_pct']:.0%}", _money(s["signing_downpayment"]),
         "At the Agreement for Lease, by CPF and/or cash. Includes the option fee. Stamp duty and legal fees "
         "are also due around now."),
        ("3 · Keys", "Loan disbursed", _money(loan["loan"]),
         "The loan is disbursed and the rest of the downpayment (after grants) is paid."),
        ("4 · Every month", "Instalment", _money(loan["monthly_instalment"]),
         f"For {loan['tenure_years']} years, by CPF OA and/or cash."),
    ]
    html = "".join(f'<div class="tl"><div class="n">{n}</div><div class="t">{t}</div><div class="v">{v}</div>'
                   f'<div class="d">{d}</div></div>' for n, t, v, d in steps)
    st.markdown(f'<div class="timeline">{html}</div>', unsafe_allow_html=True)
    deferred = policy.node("payment_stages", "downpayment_at_signing")["deferred_income_assessment"]
    st.caption(_md(f"Young couples on deferred income assessment pay {deferred:.1%} at signing instead. "
                   f"At signing you'd have {_money(a['inputs']['cpf_oa_total'])} CPF OA and "
                   f"{_money(a['inputs']['cash_savings'])} cash available."))


def render_results(a: dict | None) -> None:
    with right:
        if not a:
            st.info("👋 Tell the agent about your household, or pick an example above. "
                    "Your numbers appear here.")
            return

        icon, label, c1, c2, ink = VERDICTS[a["cash"]["verdict"]]
        lender = "bank loan" if a["loan"].get("lender") == "bank" else "HDB loan"
        st.markdown(
            f"""<div class="verdict" style="background: linear-gradient(120deg, {c1}, {c2}); color: {ink};">
                  <div class="label">Verdict · {_money(a['inputs']['flat_price'])}
                    {FLAT_LABELS.get(a['inputs']['flat_type'], a['inputs']['flat_type'])} · {lender}</div>
                  <div class="big"><span class="icon">{icon}</span> {label}</div>
                  <div class="why">{verdict_reason(a)}</div>
                </div>""",
            unsafe_allow_html=True,
        )

        cash, loan = a["cash"], a["loan"]
        row1, row2 = st.columns(2), st.columns(2)
        m1, m2, m3, m4 = *row1, *row2
        m1.metric("Grant (EHG)", _money(a["grant"]["grant"]), border=True, help=_md(a["grant"]["explanation"]))
        m2.metric(f"{'Bank' if loan.get('lender') == 'bank' else 'HDB'} loan", _money(loan["loan"]), border=True,
                  help=f"Limited by the {loan['binding_limit_label']}.")
        m3.metric("Monthly instalment", _money(loan["monthly_instalment"]), border=True,
                  delta=f"{loan['msr_used_pct']:.1f}% of income" if loan["msr_used_pct"] is not None else None,
                  delta_color="off", delta_arrow="off",
                  help=f"{loan['tenure_years']}-year tenure at {loan['interest_rate']:.2%}.")
        if cash["gap"] > 0:
            m4.metric("Cash gap", _money(cash["gap"]), border=True, delta="short of the cash needed",
                      delta_color="red", delta_arrow="off")
        else:
            m4.metric("Cash left after buying", _money(cash["cash_left_after"]), border=True)

        tabs = st.tabs(["💸 Money", "📈 Rates", "🏦 HDB vs bank", "🗓️ Payments", "🎁 Grants", "📋 Sources"])
        with tabs[0]:
            st.plotly_chart(waterfall_chart(a), width="stretch", config={"displayModeBar": False})
            st.caption(f"Flat price minus the grant and loan is the downpayment. CPF OA pays first, then cash. "
                       f"Loan limited by: **{loan['binding_limit_label']}**.")
        with tabs[1]:
            if loan["msr_used_pct"] is None:
                st.info("No loan: this household isn't eligible.")
            else:
                g, k = st.columns([1, 1])
                with g:
                    st.plotly_chart(msr_gauge(a), width="stretch", config={"displayModeBar": False})
                with k:
                    st.metric("Total interest over the loan", _money(loan["total_interest"]))
                    st.metric("Tenure", f"{loan['tenure_years']} years")
                    st.metric("Loan sized at", f"{loan['assessment_rate']:.1%}",
                              help="Lenders size the loan at a stress-test rate, so the real instalment lands "
                                   f"under the {policy.value('hdb_loan', 'msr'):.0%} cap.")
                st.markdown("**What if the interest rate changes?**")
                st.plotly_chart(rate_curve(a), width="stretch", config={"displayModeBar": False})
                st.caption("Same loan and tenure at different rates. Bank rates float; the HDB rate is pegged to "
                           "the CPF OA rate + 0.1% and reviewed quarterly.")
        with tabs[2]:
            render_comparison(a)
        with tabs[3]:
            render_timeline(a)
            st.markdown("**One-off costs**")
            st.plotly_chart(upfront_chart(a), width="stretch", config={"displayModeBar": False})
            st.caption(_md(f"Total upfront: **{_money(a['upfront']['total'])}**. "
                           "⚠️ Faded, striped bars are placeholders still being verified."))
        with tabs[4]:
            st.plotly_chart(grant_ladder(a), width="stretch", config={"displayModeBar": False})
            st.caption(_md(f"{a['grant']['explanation']} Lower incomes get bigger grants; "
                           "above the ceiling it's $0."))
        with tabs[5]:
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
                  "Source": i["source_url"]} for i in policy.sourced_items() if not i["rule"].startswith("projects.")],
                hide_index=True, width="stretch",
                column_config={"Source": st.column_config.LinkColumn(
                    display_text=r"https?://(?:www\.)?([^/]+)")},
            )


def render_comparison(a: dict) -> None:
    if a["cash"]["verdict"] == "ineligible":
        st.info("This household isn't eligible to buy a new flat, so neither loan applies.")
        return
    req = {**a["request"], "tenure_years": None, "desired_loan": None}
    bank_rate = st.session_state.get("f_bank_rate", BANK_RATE_DEFAULT * 100) / 100
    hdb = assess_household(**{**req, "lender": "hdb"})
    bank = assess_household(**{**req, "lender": "bank", "bank_rate": a["request"].get("bank_rate") or bank_rate})
    rows = [
        ("Interest rate", lambda x: f"{x['loan']['interest_rate']:.2%}"),
        ("Rate type", lambda x: "Pegged to CPF OA + 0.1%" if x["loan"]["lender"] == "hdb" else "Market, can change"),
        ("Max loan (LTV)", lambda x: f"{_money(x['loan']['loan'])} ({x['loan']['ltv']:.0%})"),
        ("Tenure", lambda x: f"{x['loan']['tenure_years']} years"),
        ("Monthly instalment", lambda x: _money(x["loan"]["monthly_instalment"])),
        ("Total interest", lambda x: _money(x["loan"]["total_interest"])),
        ("Downpayment at signing", lambda x: f"{x['stages']['signing_pct']:.0%} · "
                                             f"{_money(x['stages']['signing_downpayment'])}"),
        ("Must be paid in cash", lambda x: f"{x['loan']['min_cash_pct']:.0%} of price"),
        ("Cash needed in total", lambda x: _money(x["cash"]["total_cash_needed"])),
        ("Verdict", lambda x: f"{VERDICTS[x['cash']['verdict']][0]} {VERDICTS[x['cash']['verdict']][1]}"),
    ]
    st.dataframe([{"": name, "🏛️ HDB loan": f(hdb), "🏦 Bank loan": f(bank)} for name, f in rows],
                 hide_index=True, width="stretch")
    st.plotly_chart(interest_bars(hdb, bank), width="stretch", config={"displayModeBar": False})
    st.caption("Each loan at its longest standard tenure and largest amount. Bank rates are a market snapshot "
               "unless you enter your own quote in step ④; they usually change after a lock-in period. "
               "This is a comparison, not a recommendation.")


# ---------- left panel: calculator ----------
def form_request() -> dict:
    s = st.session_state
    applicants = [1] if s.f_household == "single" else [1, 2]
    if s.f_project == CUSTOM:
        flat_price, flat_type = s.f_custom_price, s.f_custom_type
    else:
        flat_price, flat_type = s.f_price, s.f_flat_type
    return dict(
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
        lender=s.f_lender,
        bank_rate=s.f_bank_rate / 100 if s.f_lender == "bank" else None,
    )


def _keep(key: str, low: float, high: float, default: float) -> None:
    """Re-assert a slider's value before drawing it. A slider whose range changes is a new widget to Streamlit and
    would otherwise reset to its minimum; out-of-range or missing values fall back to the default."""
    value = st.session_state.get(key)
    st.session_state[key] = value if value is not None and low <= value <= high else default


def _step(n: str, title: str) -> None:
    st.markdown(f'<div class="step"><span>{n}</span>{title}</div>', unsafe_allow_html=True)


def render_form() -> None:
    with left:
        with st.container(border=True, key="card-who"):
            _step("1", "Who's applying?")
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
            t1, t2 = st.columns(2)
            t1.toggle("All SG citizens", key="f_citizens")
            t2.toggle("First-time buyers", key="f_first")

        with st.container(border=True, key="card-savings"):
            _step("2", "Savings and timing")
            st.slider("Cash savings", 0, 300000, step=1000, format="$%d", key="f_cash")
            c1, c2 = st.columns(2)
            c1.slider("Saving each month", 0, 10000, step=100, format="$%d", key="f_monthly_savings")
            c2.slider("Years until keys", 0, 8, key="f_years")

        with st.container(border=True, key="card-flat"):
            _step("3", "Which flat?")
            pid = st.session_state.f_project
            if pid == CUSTOM:
                c3, c4 = st.columns([2, 1])
                c3.slider("Flat price", 100000, 1000000, step=5000, format="$%d", key="f_custom_price")
                c4.selectbox("Flat type", FLAT_TYPES, key="f_custom_type", format_func=lambda t: FLAT_LABELS.get(t, t))
            else:
                p = PROJECTS[pid]
                st.markdown(f"**{p['name']}** · {p['town']}  \n<small>Change the project on the map above.</small>",
                            unsafe_allow_html=True)
                st.segmented_control("Flat type", p["flat_types"], key="f_flat_type", required=True,
                                     on_change=on_flat_type_change, format_func=lambda t: FLAT_LABELS.get(t, t),
                                     width="stretch")
                r = get_project_price(pid, st.session_state.f_flat_type)
                _keep("f_price", r["price_low"], r["price_high"], r["price_low"])
                st.slider("Price within the range (floor, view and size vary)", r["price_low"], r["price_high"],
                          step=1000, format="$%d", key="f_price")

        with st.container(border=True, key="card-pay"):
            _step("4", "How will you pay?")
            st.segmented_control("Loan", ["hdb", "bank"], key="f_lender", required=True, on_change=on_lender_change,
                                 format_func=lambda x: "🏛️ HDB loan" if x == "hdb" else "🏦 Bank loan",
                                 label_visibility="collapsed", width="stretch")
            if st.session_state.f_lender == "bank":
                st.slider("Bank interest rate (% a year)", 1.0, 5.0, step=0.05, format="%.2f%%", key="f_bank_rate",
                          help=_md(f"Default is a market snapshot of advertised packages "
                                   f"({policy.node('bank_loan', 'indicative_rate')['as_of']}). "
                                   "Enter the rate you're actually quoted."))
            else:
                st.caption(f"HDB concessionary rate **{policy.value('hdb_loan', 'interest_rate'):.1%}** "
                           "(CPF OA rate + 0.1%).")

            req = form_request()
            pre = assess_household(**req)["loan"]
            max_t = pre["max_tenure_years"]
            if max_t >= 5:
                _keep("f_tenure", 5, max_t, max(5, min(pre["tenure_years"], max_t)))
                st.slider("Loan tenure (years)", 5, max_t, key="f_tenure",
                          help="Longer = smaller instalments but more interest. Bank loans over 25 years drop "
                               "the LTV to 55%." if st.session_state.f_lender == "bank" else
                               "Longer = smaller instalments but more interest.")
                req["tenure_years"] = st.session_state.f_tenure
            max_l = int(assess_household(**req)["loan"]["max_loan"])
            st.toggle("Borrow the maximum I'm allowed", key="f_borrow_max")
            if not st.session_state.f_borrow_max and max_l >= 1000:
                _keep("f_borrow", 0, max_l, max_l)
                st.slider("Amount to borrow", 0, max_l, step=1000, format="$%d", key="f_borrow")
                req["desired_loan"] = st.session_state.f_borrow

    st.session_state.assessment = assess_household(**req)


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


# ---------- page ----------
render_explorer()

st.markdown('<div class="section">🧮 Check your affordability'
            '<small>Start from an example, then make it yours.</small></div>', unsafe_allow_html=True)
ex_cols = st.columns([1, 1, 1, 0.7])
for col, label in zip(ex_cols, EXAMPLES):
    col.button(label, on_click=load_example, args=(label,), width="stretch")
ex_cols[-1].button("↺  Start over", on_click=start_over, width="stretch", type="tertiary")

left, right = st.columns([5, 7], gap="large")

if key_available and mode == CHAT_MODE:
    render_chat()
else:
    render_form()

render_results(st.session_state.assessment)

st.markdown(f'<div class="foot">{policy.value("meta", "disclaimer")} · Policy as of {policy.as_of()} · '
            f'Project prices: HDB launch annexes (Feb and Jun 2026); November 2026 prices are not out yet.</div>',
            unsafe_allow_html=True)
