"""Every Plotly chart in the app. Pure functions: data in, figure out. Numbers come from the calculators."""
from __future__ import annotations

import plotly.graph_objects as go

from calculators import get_ehg_grant, get_project_price, monthly_instalment, policy

from .theme import AQUA, BLUE, CLASS_COLOURS, FLAT_LABELS, MUTED, ORANGE, RED, money

NO_BAR = {"displayModeBar": False}


def _style(fig: go.Figure, height: int) -> go.Figure:
    fig.update_layout(height=height, margin=dict(t=30, b=10, l=10, r=10), showlegend=False,
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, sans-serif", size=13), hoverlabel=dict(font_size=13))
    fig.update_yaxes(gridcolor="rgba(137,135,129,.25)", zeroline=False)
    fig.update_xaxes(showgrid=False)
    return fig


def _class(p: dict) -> str:
    return p["classification"].split(" ")[0]


def project_map(visible: list[dict], selected: dict | None, dark: bool) -> go.Figure:
    fig = go.Figure()
    for cls, colour in CLASS_COLOURS.items():
        for status, opacity in (("launched", 0.95), ("upcoming", 0.55)):
            pts = [p for p in visible if _class(p) == cls and p["status"] == status]
            if not pts:
                continue
            fig.add_trace(go.Scattermap(
                lat=[p["location"]["lat"] for p in pts], lon=[p["location"]["lon"] for p in pts], mode="markers",
                marker=dict(size=[11 + p["units"] / 160 for p in pts], color=colour, opacity=opacity),
                customdata=[[p["name"], p["town"], p["classification"], p["exercise"], f"{p['units']:,}"]
                            for p in pts],
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>"
                              "%{customdata[3]} · %{customdata[4]} flats<extra></extra>",
            ))
    if selected:
        fig.add_trace(go.Scattermap(
            lat=[selected["location"]["lat"]], lon=[selected["location"]["lon"]], mode="markers+text",
            marker=dict(size=34, color="rgba(235,104,52,.28)"), text=[f"  {selected['name']}"],
            textposition="middle right", textfont=dict(size=13, color=ORANGE), hoverinfo="skip"))
    fig.update_layout(map=dict(style="carto-darkmatter" if dark else "carto-positron",
                               center=dict(lat=1.352, lon=103.835), zoom=10.15),
                      height=430, margin=dict(t=0, b=0, l=0, r=0), paper_bgcolor="rgba(0,0,0,0)", showlegend=False)
    return fig


def map_legend() -> str:
    dots = "".join(f'<span><i style="background:{c}"></i>{name}</span>' for name, c in CLASS_COLOURS.items())
    return (f'<div class="legend">{dots}<span><i style="background:{MUTED};opacity:.45"></i>faded = upcoming</span>'
            f'<span>◯ size = number of flats · locations approximate</span></div>')


def price_dumbbell(project: dict, flat_type: str, price: float) -> go.Figure:
    rows = [(FLAT_LABELS.get(t, t), get_project_price(project["project_id"], t)) for t in project["flat_types"]]
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
    steps = [("Flat price", "absolute", price, money(price)),
             ("Grant", "relative", -grant, f"−{money(grant)}"),
             ("Loan", "relative", -loan, f"−{money(loan)}"),
             ("CPF OA", "relative", -cash["from_cpf_oa"], f"−{money(cash['from_cpf_oa'])}"),
             ("Cash for<br>downpayment", "total", 0, money(cash["cash_for_downpayment"])),
             ("Upfront<br>costs", "relative", cash["upfront_costs"], f"+{money(cash['upfront_costs'])}")]
    if cash.get("renovation"):
        steps.append(("Renovation", "relative", cash["renovation"], f"+{money(cash['renovation'])}"))
    steps.append(("Total cash<br>needed", "total", 0, money(cash["total_cash_needed"])))
    fig = go.Figure(go.Waterfall(
        orientation="v", x=[s[0] for s in steps], measure=[s[1] for s in steps], y=[s[2] for s in steps],
        text=[s[3] for s in steps], textposition="outside", hovertemplate="%{x}: %{text}<extra></extra>",
        decreasing={"marker": {"color": AQUA}}, increasing={"marker": {"color": ORANGE}},
        totals={"marker": {"color": BLUE}}, connector={"line": {"width": 1, "color": MUTED, "dash": "dot"}},
    ))
    fig.update_yaxes(tickprefix="$", tickformat="~s", title=None)
    return _style(fig, 380)


def msr_gauge(a: dict) -> go.Figure:
    msr_pct = policy.value("hdb_loan", "msr") * 100
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=a["loan"]["msr_used_pct"] or 0,
        number={"suffix": "%", "font": {"size": 42}},
        title={"text": "of income on the loan", "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, msr_pct + 10], "ticksuffix": "%"},
            "bar": {"color": BLUE, "thickness": 0.35},
            "steps": [{"range": [0, msr_pct], "color": "rgba(42,120,214,.12)"},
                      {"range": [msr_pct, msr_pct + 10], "color": "rgba(208,59,59,.12)"}],
            "threshold": {"line": {"color": RED, "width": 3}, "thickness": 0.9, "value": msr_pct},
        },
    ))
    return _style(fig, 240)


def rate_curve(a: dict, bank_rate: float) -> go.Figure:
    """Monthly instalment on this loan across interest rates, with the HDB, bank and stress-test rates marked."""
    loan, tenure = a["loan"]["loan"], a["loan"]["tenure_years"]
    rates = [x / 1000 for x in range(10, 61)]  # 1.0% to 6.0%
    curve = [monthly_instalment(loan, r, tenure) for r in rates]
    fig = go.Figure(go.Scatter(x=[r * 100 for r in rates], y=curve, mode="lines", line=dict(color=BLUE, width=2.5),
                               hovertemplate="At %{x:.1f}%: %{y:$,.0f}/month<extra></extra>"))
    marks = [("HDB", policy.value("hdb_loan", "interest_rate"), BLUE), ("Your bank rate", bank_rate, ORANGE),
             ("MAS stress test", policy.value("bank_loan", "assessment_rate_floor"), MUTED)]
    for name, r, colour in marks:
        y = monthly_instalment(loan, r, tenure)
        fig.add_trace(go.Scatter(x=[r * 100], y=[y], mode="markers+text", text=[f"{name}<br>{money(y)}"],
                                 textposition="bottom right" if name == "Your bank rate" else "top left",
                                 marker=dict(size=11, color=colour, line=dict(color="#fff", width=2)),
                                 hovertemplate=f"{name} %{{x:.2f}}%: %{{y:$,.0f}}/month<extra></extra>"))
    cap = a["loan"].get("msr_max_instalment")
    if cap:
        fig.add_hline(y=cap, line_dash="dot", line_color=RED, annotation_position="top left",
                      annotation_text=f"{policy.value('hdb_loan', 'msr'):.0%} of income = {money(cap)}")
    ys = curve + [cap or 0]
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
                             text=[f"You: {money(you_grant)}"], textposition="top right",
                             hovertemplate="Your income $%{x:,} → grant $%{y:,}<extra></extra>"))
    fig.add_vline(x=ceiling, line_dash="dot", line_color=MUTED,
                  annotation_text=f"EHG ceiling {money(ceiling)}", annotation_position="top left")
    fig.update_xaxes(title="Average gross monthly household income", tickprefix="$", tickformat=",")
    fig.update_yaxes(title=None, tickprefix="$", tickformat="~s")
    return _style(fig, 300)


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
        x=[r[1] for r in rows], y=[r[0] + ("" if verified.get(r[2]) else "  ⚠️") for r in rows], orientation="h",
        marker=dict(color=[ORANGE if verified.get(r[2]) else "rgba(235,104,52,.30)" for r in rows],
                    pattern=dict(shape=["" if verified.get(r[2]) else "/" for r in rows],
                                 fgcolor=ORANGE, solidity=0.4)),
        text=[money(r[1]) for r in rows], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    fig.update_xaxes(visible=False, range=[0, max(r[1] for r in rows) * 1.2])
    return _style(fig, 240)


def interest_bars(hdb: dict, bank: dict) -> go.Figure:
    names = [f"HDB loan<br>{hdb['loan']['interest_rate']:.2%}", f"Bank loan<br>{bank['loan']['interest_rate']:.2%}"]
    vals = [hdb["loan"]["total_interest"], bank["loan"]["total_interest"]]
    fig = go.Figure(go.Bar(x=names, y=vals, marker=dict(color=[BLUE, ORANGE]), width=0.45,
                           text=[money(v) for v in vals], textposition="outside", cliponaxis=False,
                           hovertemplate="%{x}: %{text} total interest<extra></extra>"))
    fig.update_yaxes(visible=False, range=[0, max(vals + [1]) * 1.25])
    fig.update_layout(title=dict(text="Total interest over the loan", font=dict(size=14)))
    return _style(fig, 270)


def projection_chart(rows: list[dict]) -> go.Figure:
    """Cash left (above zero) or cash gap (below zero) if you apply now or in later years."""
    labels = ["Now" if r["years_from_now"] == 0 else f"+{r['years_from_now']} yr" for r in rows]
    values = [r["cash_left_after"] if r["gap"] == 0 else -r["gap"] for r in rows]
    colours = [MUTED if r["verdict"] == "ineligible" else (BLUE if v >= 0 else RED) for r, v in zip(rows, values)]
    texts = ["not eligible" if r["verdict"] == "ineligible" else (f"+{money(v)}" if v >= 0 else f"−{money(-v)}")
             for r, v in zip(rows, values)]
    fig = go.Figure(go.Bar(x=labels, y=values, marker=dict(color=colours), text=texts, textposition="outside",
                           cliponaxis=False, hovertemplate="%{x}: %{text}<extra></extra>"))
    fig.add_hline(y=0, line_color=MUTED, line_width=1)
    fig.update_yaxes(tickprefix="$", tickformat="~s", title=None)
    fig.update_layout(title=dict(text="Cash left after buying (blue) or short (red)", font=dict(size=14)))
    return _style(fig, 320)
