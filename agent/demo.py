"""Free agent demo: replays the tool calls Claude makes for an example question, on the real calculators.

No API call is made. The tool calls and every number are real; the answer's wording is a fixed template that mirrors
the structure the system prompt asks Claude for. The UI labels it as a replay, never as Claude.
"""
from __future__ import annotations

from typing import Any

from calculators import policy

from .agent import AgentTurn, ToolCall
from .tools import run_tool

VERDICT_LINES = {
    "affordable": "✅ **Affordable.** You can cover the cash needed and keep an emergency buffer.",
    "tight": "⚠️ **Tight.** You can pay, but you'd keep less than the suggested emergency buffer.",
    "gap": "⛔ **Cash gap.** You'd be short of the cash needed.",
    "ineligible": "🚫 **Not eligible** for a new flat with these details.",
}


def demo_turn(request: dict[str, Any], project_id: str | None = None, flat_type: str = "4-room") -> AgentTurn:
    """Run the same tool sequence the agent uses, then write the answer from a template."""
    calls: list[ToolCall] = []

    def call(name: str, tool_input: dict[str, Any]) -> Any:
        output, is_error = run_tool(name, tool_input)
        calls.append(ToolCall(name, tool_input, output, is_error))
        return output

    price_info = None
    if project_id:
        call("list_projects", {})
        price_info = call("get_project_price", {"project_id": project_id, "flat_type": flat_type})
        request = {**request, "flat_price": price_info["price_used"], "flat_type": flat_type}
    a = call("assess_household", request)
    return AgentTurn(text=format_answer(a, price_info), tool_calls=calls, last_assessment=a)


def _money(x: float) -> str:
    return f"\\${x:,.0f}"  # escaped for Streamlit markdown


def format_answer(a: dict, price_info: dict | None = None) -> str:
    loan, cash, grant = a["loan"], a["cash"], a["grant"]
    lines = [VERDICT_LINES[cash["verdict"]], ""]
    if price_info:
        lines += [f"Price used: {_money(price_info['price_used'])} for a {price_info['flat_type']} at "
                  f"{price_info['project']} ({price_info['price_basis']}).", ""]
    rows = [
        ("Flat price", _money(a["inputs"]["flat_price"])),
        ("Grant (EHG)", _money(grant["grant"])),
        ("Loan", _money(loan["loan"])),
        ("Monthly instalment", f"{_money(loan['monthly_instalment'])}"
                               + (f" ({loan['msr_used_pct']:.1f}% of income)" if loan["msr_used_pct"] else "")),
        ("Downpayment", _money(cash["downpayment"])),
        ("From CPF OA", _money(cash["from_cpf_oa"])),
        ("Total cash needed", _money(cash["total_cash_needed"])),
        ("Cash gap" if cash["gap"] else "Cash left after", _money(cash["gap"] or cash["cash_left_after"])),
    ]
    lines += ["| | |", "|---|---|", *[f"| {k} | {v} |" for k, v in rows], ""]
    if cash["verdict"] != "ineligible":
        lines += [f"The loan is limited by the **{loan['binding_limit_label']}**.", ""]
    lines += ["**Assumptions**", *[f"- {x.replace('$', chr(92) + '$')}" for x in a["assumptions"]], ""]
    lines += ["**Confirm with HDB:** your HFE letter, the final price at launch, and the grant amount."]
    lines += ["", policy.value("meta", "disclaimer")]
    return "\n".join(lines)
