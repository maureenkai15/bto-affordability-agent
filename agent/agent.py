"""The agentic loop: Claude decides which calculator to call, we run it, repeat until it can answer."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from calculators import policy

from .tools import TOOLS, run_tool, to_json

MODEL = os.getenv("BTO_AGENT_MODEL", "claude-sonnet-5-5")
MAX_STEPS = 12
PLACEHOLDER_KEY = "sk-ant-..."  # the value shipped in .env.example


def has_api_key() -> bool:
    """True only for a real-looking key. Without one the app stays in free form mode and never calls the API."""
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return key.startswith("sk-ant-") and key != PLACEHOLDER_KEY

SYSTEM_PROMPT = f"""You help Singapore residents check whether they can afford a BTO flat.
Policy values are as of {policy.as_of()}.

How you work:
- You NEVER do arithmetic yourself. Every number in your answer must come from a tool result.
- If inputs are missing, ask for them in ONE short message. You need: household type (couple or single),
  each person's age and gross monthly income, combined CPF Ordinary Account balance, cash savings,
  first-timer status, whether all applicants are Singapore citizens, and which flat (project + type) or a price.
  Also ask roughly how many years until key collection (BTOs usually take several years) and monthly savings.
- When a project or town is named (e.g. Tengah, Bedok), call list_projects, then get_project_price. Use the low end
  unless asked, and say whether the price is an HDB launch price, an estimate, or a comparable project's price.
- Loans: HDB loan by default. If the user asks about a bank loan, pass lender="bank" and their quoted rate.
  Use tenure_years / desired_loan for "shorter loan" or "borrow less" what-ifs. Never recommend a lender.
- For "what if we wait / apply in N years", call project_household with the assess_household arguments.
- Once you have everything, call assess_household. Use the single tools for what-ifs and to explain a step.

How you answer:
1. Verdict in one line: affordable, tight, gap, or not eligible.
2. A short markdown table of the key numbers (price, grant, loan, monthly instalment and % of income,
   downpayment, from CPF, cash needed, gap or cash left).
3. Which loan limit bound and why, in one sentence.
4. Assumptions (bullet list), including the policy as-of date and that prices are indicative.
5. What to confirm with HDB, and any warnings from the tools.
End with: "Estimate only. Your HFE letter from HDB is the official answer. Not financial advice."

Never recommend a specific flat, bank or financial product. Be plain, warm and concise.
"""


@dataclass
class ToolCall:
    name: str
    input: dict[str, Any]
    output: dict[str, Any]
    is_error: bool


@dataclass
class AgentTurn:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    last_assessment: dict[str, Any] | None = None


def run_agent(messages: list[dict[str, Any]], client: Anthropic | None = None) -> AgentTurn:
    """Run one user turn. `messages` is the running conversation and is extended in place."""
    client = client or Anthropic()
    calls: list[ToolCall] = []
    assessment: dict[str, Any] | None = None

    for _ in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            return AgentTurn(text=text, tool_calls=calls, last_assessment=assessment)

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            output, is_error = run_tool(block.name, block.input)
            calls.append(ToolCall(block.name, block.input, output, is_error))
            if block.name == "assess_household" and not is_error:
                assessment = output
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": to_json(output),
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": results})

    return AgentTurn(
        text="I couldn't finish the calculation in a reasonable number of steps. Could you restate your details?",
        tool_calls=calls,
        last_assessment=assessment,
    )
