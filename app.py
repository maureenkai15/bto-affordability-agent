"""Streamlit UI: live calculator and agent demo (both free), plus optional chat with Claude when an API key is set.

Run:  streamlit run app.py
"""
from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from agent import has_api_key, run_agent
from agent.demo import demo_turn
from calculators import assess_household, get_project_price, list_projects, policy, project_household
from calculators.assess import EMERGENCY_BUFFER_MONTHS
from ui import charts
from ui.explain import jargon, plain_summary
from ui.theme import CLASS_COLOURS, CSS, FLAT_LABELS, VERDICTS, badge, md, money

load_dotenv()  # local dev: reads ANTHROPIC_API_KEY from .env
if "ANTHROPIC_API_KEY" not in os.environ:
    try:  # Streamlit Cloud: reads it from the app's Secrets; raises if no secrets file exists
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
    except Exception:  # noqa: BLE001
        pass

st.set_page_config(page_title="BTO Affordability Agent", page_icon="🏠", layout="wide")

FORM_MODE = "🧮 Calculator"
DEMO_MODE = "🤖 Agent demo"
CHAT_MODE = "💬 Chat with Claude"
CUSTOM = "custom"
REGIONS = ["North", "North-East", "East", "West", "Central"]

PROJECTS = {p["project_id"]: p for p in list_projects()}
FLAT_TYPES = list(policy.node("upfront", "option_fee", "by_flat_type"))
BANK_RATE_DEFAULT = policy.value("bank_loan", "indicative_rate")

# Each example drives every mode: a chat prompt, and the same household as calculator values.
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
                 f_debts=0, f_reno=0, f_regions=REGIONS, f_status="All",
                 f_wait_years=3, f_income_growth=0.0, f_price_growth=0.0)
FORM_DEFAULTS = BASE_FORM | next(iter(EXAMPLES.values()))["form"]  # open on a filled-in example, not zeros
RESETTABLE = ("f_tenure", "f_borrow")  # depend on other inputs; recomputed when cleared

# ---------- state ----------
if "api_messages" not in st.session_state:
    st.session_state.api_messages = []      # what the model sees (includes tool calls)
    st.session_state.chat = []              # what the user sees
    st.session_state.tool_log = []
    st.session_state.assessment = None
    st.session_state.demo_chat = []         # (prompt, AgentTurn) pairs replayed in demo mode
for k, v in FORM_DEFAULTS.items():
    st.session_state.setdefault(k, v)
st.session_state.setdefault("f_exact", False)

key_available = has_api_key()


def example_request(form: dict) -> tuple[dict, str | None, str]:
    """An example's calculator values as assess_household arguments, plus its project and flat type."""
    f = BASE_FORM | form
    applicants = [1] if f["f_household"] == "single" else [1, 2]
    request = dict(household_type=f["f_household"], incomes=[f[f"f_inc{i}"] for i in applicants],
                   ages=[f[f"f_age{i}"] for i in applicants], cpf_oa_balances=[f[f"f_oa{i}"] for i in applicants],
                   cash_savings=f["f_cash"], flat_price=f["f_custom_price"], flat_type=f["f_custom_type"],
                   years_until_key_collection=f["f_years"], monthly_savings=f["f_monthly_savings"])
    if f["f_project"] == CUSTOM:
        return request, None, f["f_custom_type"]
    return request, f["f_project"], f["f_flat_type"]


def load_example(label: str) -> None:
    mode = st.session_state.get("mode")
    if mode == CHAT_MODE:
        st.session_state.pending_prompt = EXAMPLES[label]["prompt"]
    elif mode == DEMO_MODE:
        st.session_state.pending_demo = label
    else:
        for k in RESETTABLE:
            st.session_state.pop(k, None)
        st.session_state.update(BASE_FORM | EXAMPLES[label]["form"])


def start_over() -> None:
    for k in ("api_messages", "chat", "tool_log", "assessment", "demo_chat", *FORM_DEFAULTS, *RESETTABLE):
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


def _keep(key: str, low: float, high: float, default: float) -> None:
    """Re-assert a slider's value before drawing it. A slider whose range changes is a new widget to Streamlit and
    would otherwise reset to its minimum; out-of-range or missing values fall back to the default."""
    value = st.session_state.get(key)
    st.session_state[key] = value if value is not None and low <= value <= high else default


def amount(label: str, key: str, high: int, step: int, help: str | None = None, target=st) -> None:
    """A money input: a slider, or a box to type an exact amount when 'Type exact numbers' is on."""
    _keep(key, 0, high, 0)  # swapping slider <-> box makes a new widget; keep the value across the swap
    if st.session_state.f_exact:
        target.number_input(label, 0, high, step=step, key=key, help=help)
    else:
        target.slider(label, 0, high, step=step, format="$%d", key=key, help=help)


# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### ⚙️ Mode")
    modes = [FORM_MODE, DEMO_MODE] + ([CHAT_MODE] if key_available else [])
    mode = st.radio("Mode", modes, key="mode", label_visibility="collapsed",
                    captions=["Live sliders, free", "Watch the agent's tool calls, free"]
                    + (["Free-text questions (uses your API key)"] if key_available else []))
    if not key_available:
        st.caption("💡 Free-text chat with Claude appears here when an Anthropic API key is set (paid). "
                   "Both modes above are free.")
    st.toggle("✏️ Type exact numbers", key="f_exact", help="Swap the money sliders for boxes you can type into.")
    st.divider()
    st.markdown("### 📜 Policy snapshot")
    st.caption(f"As of **{policy.as_of()}**")
    st.markdown(md(
        f"- Income ceiling (families): **{money(policy.value('income_ceilings', 'family'))}**/month\n"
        f"- EHG grant: up to **{money(policy.node('ehg', 'family')['bands'][0]['grant'])}**\n"
        f"- HDB loan: **{policy.value('hdb_loan', 'interest_rate'):.1%}** · "
        f"LTV **{policy.value('hdb_loan', 'ltv'):.0%}** · MSR **{policy.value('hdb_loan', 'msr'):.0%}**\n"
        f"- Bank loan: LTV **{policy.value('bank_loan', 'ltv'):.0%}**, TDSR "
        f"**{policy.value('bank_loan', 'tdsr'):.0%}**, stress test "
        f"**{policy.value('bank_loan', 'assessment_rate_floor'):.0%}**"
    ))
    if policy.is_stale():
        st.warning("Policy values may be out of date. Check hdb.gov.sg.")

st.html(CSS)
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
        <div><b>{sum(i['verified'] for i in rules)}/{len(rules)}</b><span>rules verified</span></div>
      </div>
      <span class="chip">📅 Policy as of {policy.as_of()}</span>
      <span class="chip">🧮 Every number from tested Python, not AI</span>
      <span class="chip">🔗 Every rule linked to its source</span>
      <span class="chip">🆓 Free, no sign-up</span>
    </div>""",
    unsafe_allow_html=True,
)


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
        dark = getattr(getattr(st.context, "theme", None), "type", None) == "dark"
        st.plotly_chart(charts.project_map(visible, PROJECTS.get(selected), dark), width="stretch",
                        config={**charts.NO_BAR, "scrollZoom": False})
        st.markdown(charts.map_legend(), unsafe_allow_html=True)
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
            st.markdown("**Enter any price** in step ③ below.")
            return
        p = PROJECTS[selected]
        badges = badge(p["classification"], CLASS_COLOURS[p["classification"].split(" ")[0]]) + \
            badge(p["exercise"]) + badge("Upcoming · prices at launch" if p["status"] == "upcoming" else "Launched")
        wait = f" · ~{p['waiting_time_months']} months to keys" if p.get("waiting_time_months") else ""
        st.markdown(f'<div class="pcard"><h3>{p["name"]}</h3><div class="meta">{p["town"]} · {p["region"]} · '
                    f'{p["units"]:,} flats{wait}</div>{badges}</div>', unsafe_allow_html=True)
        r = get_project_price(selected, st.session_state.f_flat_type)
        if "error" not in r and p["status"] == "upcoming":
            st.markdown(f'<div class="basis">⚠️ Not HDB prices. {r["price_basis"].capitalize()}.</div>',
                        unsafe_allow_html=True)
        st.plotly_chart(charts.price_dumbbell(p, st.session_state.f_flat_type, st.session_state.f_price),
                        width="stretch", config=charts.NO_BAR)
        st.caption("Indicative price ranges before grants. ◆ = the price you're testing.")


# ---------- right panel: results ----------
def verdict_reason(a: dict) -> str:
    cash, verdict = a["cash"], a["cash"]["verdict"]
    if verdict == "ineligible":
        return " ".join(a["eligibility"]["reasons"]) or "This household does not meet the eligibility rules."
    if verdict == "gap":
        months = a.get("months_to_close_gap")
        extra = f" At your saving rate that's about {months} months." if months else ""
        return f"You'd be {money(cash['gap'])} short in cash.{extra}"
    if verdict == "tight":
        return (f"You can pay, but you'd keep only {money(cash['cash_left_after'])} in cash, below "
                f"{EMERGENCY_BUFFER_MONTHS} months of instalments ({money(cash['cash_buffer_target'])}).")
    return (f"You'd still have {money(cash['cash_left_after'])} in cash after buying, above "
            f"{EMERGENCY_BUFFER_MONTHS} months of instalments ({money(cash['cash_buffer_target'])}).")


def render_timeline(a: dict) -> None:
    s, loan = a["stages"], a["loan"]
    steps = [
        ("1 · Booking", "Option fee", money(s["booking_option_fee"]), "Paid when you pick your flat."),
        ("2 · Signing", f"Downpayment {s['signing_pct']:.0%}", money(s["signing_downpayment"]),
         "At the Agreement for Lease, by CPF and/or cash. Includes the option fee. Stamp duty and legal fees "
         "are also due around now."),
        ("3 · Keys", "Loan disbursed", money(loan["loan"]),
         "The loan is disbursed and the rest of the downpayment (after grants) is paid."),
        ("4 · Every month", "Instalment", money(loan["monthly_instalment"]),
         f"For {loan['tenure_years']} years, by CPF OA and/or cash."),
    ]
    html = "".join(f'<div class="tl"><div class="n">{n}</div><div class="t">{t}</div><div class="v">{v}</div>'
                   f'<div class="d">{d}</div></div>' for n, t, v, d in steps)
    st.markdown(f'<div class="timeline">{html}</div>', unsafe_allow_html=True)
    deferred = policy.node("payment_stages", "downpayment_at_signing")["deferred_income_assessment"]
    st.caption(md(f"Young couples on deferred income assessment pay {deferred:.1%} at signing instead. "
                  f"At signing you'd have {money(a['inputs']['cpf_oa_total'])} CPF OA and "
                  f"{money(a['inputs']['cash_savings'])} cash available."))


def render_comparison(a: dict) -> None:
    if a["cash"]["verdict"] == "ineligible":
        st.info("This household isn't eligible to buy a new flat, so neither loan applies.")
        return
    req = {**a["request"], "tenure_years": None, "desired_loan": None}
    bank_rate = a["request"].get("bank_rate") or st.session_state.f_bank_rate / 100
    hdb = assess_household(**{**req, "lender": "hdb"})
    bank = assess_household(**{**req, "lender": "bank", "bank_rate": bank_rate})
    rows = [
        ("Interest rate", lambda x: f"{x['loan']['interest_rate']:.2%}"),
        ("Rate type", lambda x: "Pegged to CPF OA + 0.1%" if x["loan"]["lender"] == "hdb" else "Market, can change"),
        ("Max loan (LTV)", lambda x: f"{money(x['loan']['loan'])} ({x['loan']['ltv']:.0%})"),
        ("Limited by", lambda x: x["loan"]["binding_limit_label"]),
        ("Tenure", lambda x: f"{x['loan']['tenure_years']} years"),
        ("Monthly instalment", lambda x: money(x["loan"]["monthly_instalment"])),
        ("Total interest", lambda x: money(x["loan"]["total_interest"])),
        ("Downpayment at signing", lambda x: f"{x['stages']['signing_pct']:.0%} · "
                                             f"{money(x['stages']['signing_downpayment'])}"),
        ("Must be paid in cash", lambda x: f"{x['loan']['min_cash_pct']:.0%} of price"),
        ("Cash needed in total", lambda x: money(x["cash"]["total_cash_needed"])),
        ("Verdict", lambda x: f"{VERDICTS[x['cash']['verdict']][0]} {VERDICTS[x['cash']['verdict']][1]}"),
    ]
    st.dataframe([{"": name, "🏛️ HDB loan": f(hdb), "🏦 Bank loan": f(bank)} for name, f in rows],
                 hide_index=True, width="stretch")
    st.plotly_chart(charts.interest_bars(hdb, bank), width="stretch", config=charts.NO_BAR)
    st.caption("Each loan at its longest standard tenure and largest amount. Bank rates are a market snapshot "
               "unless you enter your own quote in step ④; they usually change after a lock-in period. "
               "This is a comparison, not a recommendation.")


def render_wait(a: dict) -> None:
    st.markdown("**What if you apply later?** Your CPF OA grows with contributions (official 2026 rates) and "
                "interest, and your cash grows with your monthly savings.")
    w1, w2, w3 = st.columns(3)
    w1.slider("Years from now", 1, 8, key="f_wait_years")
    w2.slider("Pay rise a year (your guess)", 0.0, 8.0, step=0.5, format="%.1f%%", key="f_income_growth")
    w3.slider("Price rise a year (your guess)", 0.0, 8.0, step=0.5, format="%.1f%%", key="f_price_growth")
    rows = project_household(a["request"], st.session_state.f_wait_years,
                             income_growth=st.session_state.f_income_growth / 100,
                             price_growth=st.session_state.f_price_growth / 100)
    first = next((r for r in rows if r["verdict"] == "affordable"), None)
    if first is None:
        st.warning(f"Not affordable in any of the next {st.session_state.f_wait_years} years on these assumptions.")
    elif first["years_from_now"] == 0:
        st.success("Affordable now. The chart shows how your buffer changes if you wait.")
    else:
        st.success(md(f"Affordable in about {first['years_from_now']} year(s), with "
                      f"{money(first['cash_left_after'])} cash left."))
    lost = [r for r in rows[1:] if r["grant"] < rows[0]["grant"]]
    if lost:
        st.info(md(f"Heads up: with the pay rise, your grant falls from {money(rows[0]['grant'])} to "
                   f"{money(lost[-1]['grant'])}. Higher income means a smaller EHG."))
    st.plotly_chart(charts.projection_chart(rows), width="stretch", config=charts.NO_BAR)
    st.dataframe([{"When": "Now" if r["years_from_now"] == 0 else f"In {r['years_from_now']} yr",
                   "Income": money(r["monthly_household_income"]), "CPF OA": money(r["cpf_oa_total"]),
                   "Cash": money(r["cash_savings"]), "Price": money(r["flat_price"]), "Grant": money(r["grant"]),
                   "Verdict": f"{VERDICTS[r['verdict']][0]} {VERDICTS[r['verdict']][1]}"} for r in rows],
                 hide_index=True, width="stretch")
    st.caption("Simplified: yearly steps, monthly wages only (no bonuses), base OA interest only. "
               "The waiting time for keys after you apply stays the same.")


def render_results(a: dict | None) -> None:
    with right:
        if not a:
            st.info("👋 Pick an example above to see the agent at work. Your numbers appear here.")
            return

        icon, label, c1, c2, ink = VERDICTS[a["cash"]["verdict"]]
        lender = "bank loan" if a["loan"].get("lender") == "bank" else "HDB loan"
        st.markdown(
            f"""<div class="verdict" style="background: linear-gradient(120deg, {c1}, {c2}); color: {ink};">
                  <div class="label">Verdict · {money(a['inputs']['flat_price'])}
                    {FLAT_LABELS.get(a['inputs']['flat_type'], a['inputs']['flat_type'])} · {lender}</div>
                  <div class="big"><span class="icon">{icon}</span> {label}</div>
                  <div class="why">{verdict_reason(a)}</div>
                </div>""",
            unsafe_allow_html=True,
        )

        cash, loan = a["cash"], a["loan"]
        row1, row2 = st.columns(2), st.columns(2)
        m1, m2, m3, m4 = *row1, *row2
        m1.metric("Grant (EHG)", money(a["grant"]["grant"]), border=True, help=md(a["grant"]["explanation"]))
        m2.metric(f"{'Bank' if loan.get('lender') == 'bank' else 'HDB'} loan", money(loan["loan"]), border=True,
                  help=f"Limited by the {loan['binding_limit_label']}.")
        m3.metric("Monthly instalment", money(loan["monthly_instalment"]), border=True,
                  delta=f"{loan['msr_used_pct']:.1f}% of income" if loan["msr_used_pct"] is not None else None,
                  delta_color="off", delta_arrow="off",
                  help=f"{loan['tenure_years']}-year tenure at {loan['interest_rate']:.2%}.")
        if cash["gap"] > 0:
            m4.metric("Cash gap", money(cash["gap"]), border=True, delta="short of the cash needed",
                      delta_color="red", delta_arrow="off")
        else:
            m4.metric("Cash left after buying", money(cash["cash_left_after"]), border=True)

        with st.container(key="plain"):
            st.markdown("**💬 In plain English**")
            st.markdown("\n".join(f"- {md(x)}" for x in plain_summary(a)))

        tabs = st.tabs(["💸 Money", "📈 Rates", "🏦 HDB vs bank", "🗓️ Payments", "⏳ Wait?", "📋 Sources"])
        with tabs[0]:
            st.plotly_chart(charts.waterfall_chart(a), width="stretch", config=charts.NO_BAR)
            st.caption(f"Flat price minus the grant and loan is the downpayment. CPF OA pays first, then cash. "
                       f"Loan limited by: **{loan['binding_limit_label']}**.")
            st.markdown("**🎁 Where your grant comes from**")
            st.plotly_chart(charts.grant_ladder(a), width="stretch", config=charts.NO_BAR)
            st.caption(md(f"{a['grant']['explanation']} Lower incomes get bigger grants; "
                          "above the ceiling it's $0."))
        with tabs[1]:
            if loan["msr_used_pct"] is None:
                st.info("No loan: this household isn't eligible.")
            else:
                g, k = st.columns(2)
                with g:
                    st.plotly_chart(charts.msr_gauge(a), width="stretch", config=charts.NO_BAR)
                with k:
                    st.metric("Total interest over the loan", money(loan["total_interest"]))
                    st.metric("Tenure", f"{loan['tenure_years']} years")
                    st.metric("Loan sized at", f"{loan['assessment_rate']:.1%}",
                              help="Lenders size the loan at a stress-test rate, so the real instalment lands "
                                   f"under the {policy.value('hdb_loan', 'msr'):.0%} cap.")
                st.markdown("**What if the interest rate changes?**")
                st.plotly_chart(charts.rate_curve(a, st.session_state.f_bank_rate / 100), width="stretch",
                                config=charts.NO_BAR)
                st.caption("Same loan and tenure at different rates. Bank rates float; the HDB rate is pegged to "
                           "the CPF OA rate + 0.1% and reviewed quarterly.")
        with tabs[2]:
            render_comparison(a)
        with tabs[3]:
            render_timeline(a)
            st.markdown("**One-off costs**")
            st.plotly_chart(charts.upfront_chart(a), width="stretch", config=charts.NO_BAR)
            st.caption(md(f"Total upfront: **{money(a['upfront']['total'])}**. "
                          "⚠️ Faded, striped bars are placeholders still being verified."))
        with tabs[4]:
            render_wait(a)
        with tabs[5]:
            for note in a["eligibility"].get("notes", []):
                st.info(md(note))
            st.markdown("**Assumptions**")
            for item in a["assumptions"]:
                st.markdown(md(f"- {item}"))
            if a["warnings"]:
                st.markdown("**Warnings**")
                for w in a["warnings"]:
                    st.warning(md(w), icon="⚠️")
            st.markdown("**Where every rule comes from**")
            st.dataframe(
                [{"Rule": i["rule"], "Status": "✅ verified" if i["verified"] else "⚠️ to confirm",
                  "Source": i["source_url"]} for i in rules],
                hide_index=True, width="stretch",
                column_config={"Source": st.column_config.LinkColumn(display_text=r"https?://(?:www\.)?([^/]+)")},
            )


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
        other_monthly_debts=s.f_debts,
        renovation_budget=s.f_reno,
    )


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
                    amount("Gross monthly income", f"f_inc{i}", 20000, 100, help="Before CPF deductions.")
                    amount("CPF OA balance", f"f_oa{i}", 300000, 1000)
            t1, t2 = st.columns(2)
            t1.toggle("All SG citizens", key="f_citizens")
            t2.toggle("First-time buyers", key="f_first")

        with st.container(border=True, key="card-savings"):
            _step("2", "Savings and timing")
            amount("Cash savings", "f_cash", 300000, 1000)
            c1, c2 = st.columns(2)
            amount("Saving each month", "f_monthly_savings", 10000, 100, target=c1)
            c2.slider("Years until keys", 0, 8, key="f_years")
            amount("Renovation & furnishing budget", "f_reno", 150000, 1000,
                   help="Paid in cash; CPF can't be used for renovation. Leave at $0 to skip.")

        with st.container(border=True, key="card-flat"):
            _step("3", "Which flat?")
            pid = st.session_state.f_project
            if pid == CUSTOM:
                c3, c4 = st.columns([2, 1])
                if st.session_state.f_exact:
                    c3.number_input("Flat price", 50000, 1500000, step=5000, key="f_custom_price")
                else:
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
                          help=md(f"Default is a market snapshot of advertised packages "
                                  f"({policy.node('bank_loan', 'indicative_rate')['as_of']}). "
                                  "Enter the rate you're actually quoted."))
            else:
                st.caption(f"HDB concessionary rate **{policy.value('hdb_loan', 'interest_rate'):.1%}** "
                           "(CPF OA rate + 0.1%).")
            amount("Other monthly debts (car, study, cards)", "f_debts", 5000, 50,
                   help="Banks count these in the 55% TDSR. HDB also weighs them, which this tool doesn't model.")

            req = form_request()
            pre = assess_household(**req)["loan"]
            max_t = pre["max_tenure_years"]
            if max_t >= 5:
                _keep("f_tenure", 5, max_t, max(5, min(pre["tenure_years"], max_t)))
                st.slider("Loan tenure (years)", 5, max_t, key="f_tenure",
                          help="Longer = smaller instalments but more interest."
                          + (" Bank loans over 25 years drop the LTV to 55%." if st.session_state.f_lender == "bank"
                             else ""))
                req["tenure_years"] = st.session_state.f_tenure
            max_l = int(assess_household(**req)["loan"]["max_loan"])
            st.toggle("Borrow the maximum I'm allowed", key="f_borrow_max")
            if not st.session_state.f_borrow_max and max_l >= 1000:
                _keep("f_borrow", 0, max_l, max_l)
                st.slider("Amount to borrow", 0, max_l, step=1000, format="$%d", key="f_borrow")
                req["desired_loan"] = st.session_state.f_borrow

    st.session_state.assessment = assess_household(**req)


# ---------- left panel: agent demo and chat ----------
def render_tool_calls(calls: list) -> None:
    for i, c in enumerate(calls, 1):
        with st.expander(f"🔧 {i}. `{c.name}`" + (" ⚠️ error" if c.is_error else ""), expanded=False):
            st.json({"input": c.input, "output": c.output}, expanded=1)


def render_demo() -> None:
    with left:
        st.markdown(
            '<div class="demo">🤖 <b>Agent demo, free replay.</b> Pick an example above. The agent\'s tool calls '
            'run live on the real calculators, in the same order Claude uses. The answer\'s wording is a fixed '
            'template showing the format Claude is asked for; it is not written by Claude. '
            'Free-text questions need an API key.</div>', unsafe_allow_html=True)
        st.graphviz_chart(
            'digraph { rankdir=LR; bgcolor="transparent"; node [shape=box, style="rounded,filled", '
            'fillcolor="#eef2f8", color="#2a78d6", fontname="Inter", fontsize=11]; edge [color="#898781"]; '
            'Q [label="Your question"]; A [label="Claude agent\\npicks tools,\\nnever does maths"]; '
            'T [label="Python calculators\\n(tested)"]; P [label="policy_2026.yaml\\nsourced + dated", '
            'shape=cylinder]; R [label="Answer + charts"]; Q -> A -> T; T -> A [label=" results", fontsize=9]; '
            'P -> T; A -> R }', width="stretch")
        label = st.session_state.pop("pending_demo", None)
        if label:
            request, pid, flat_type = example_request(EXAMPLES[label]["form"])
            st.session_state.demo_chat.append((EXAMPLES[label]["prompt"], demo_turn(request, pid, flat_type)))
        for prompt, turn in st.session_state.demo_chat:
            st.chat_message("user").markdown(md(prompt))
            with st.chat_message("assistant", avatar="🤖"):
                with st.status(f"Called {len(turn.tool_calls)} tools", state="complete", expanded=False):
                    render_tool_calls(turn.tool_calls)
                st.markdown(turn.text)
                st.caption("Replay: real tool calls and numbers, template wording.")
        if st.session_state.demo_chat:
            st.session_state.assessment = st.session_state.demo_chat[-1][1].last_assessment
        st.chat_input("Free-text questions need an API key. Pick an example above.", disabled=True)


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
                render_tool_calls(st.session_state.tool_log)


# ---------- page ----------
render_explorer()

head, help_col = st.columns([4, 1], vertical_alignment="bottom")
head.markdown('<div class="section">🧮 Check your affordability'
              '<small>Start from an example, then make it yours.</small></div>', unsafe_allow_html=True)
with help_col.popover("📖 Jargon buster", width="stretch"):
    for term, meaning in jargon():
        st.markdown(md(f"**{term}**: {meaning}"))
ex_cols = st.columns([1, 1, 1, 0.7])
for col, label in zip(ex_cols, EXAMPLES):
    col.button(label, on_click=load_example, args=(label,), width="stretch")
ex_cols[-1].button("↺  Start over", on_click=start_over, width="stretch", type="tertiary")

left, right = st.columns([5, 7], gap="large")

if mode == CHAT_MODE and key_available:
    render_chat()
elif mode == DEMO_MODE:
    render_demo()
else:
    render_form()

render_results(st.session_state.assessment)

st.markdown(f'<div class="foot">{policy.value("meta", "disclaimer")} · Policy as of {policy.as_of()} · '
            f'Project prices: HDB launch annexes (Feb and Jun 2026); November 2026 prices are not out yet.</div>',
            unsafe_allow_html=True)
