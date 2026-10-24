"""Tests the agent loop with a fake Claude client: no API key or network needed."""
from types import SimpleNamespace as NS

from agent import TOOLS, run_agent, run_tool


class FakeMessages:
    """Replays scripted responses: first a tool call, then a final text answer."""

    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.calls = []

    def create(self, **kwargs):
        # snapshot: the agent extends the same list in place after each call
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.scripted.pop(0)


def tool_use(name, tool_input, id_="t1"):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", id=id_, name=name, input=tool_input)])


def final(text):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=text)])


def test_every_tool_has_a_dispatcher():
    for t in TOOLS:
        out, is_error = run_tool(t["name"], {})
        # empty input must fail cleanly (bad args), never "unknown tool"
        assert "Unknown tool" not in str(out)


def test_loop_runs_tool_then_answers():
    household = dict(household_type="family", incomes=[4500, 3500], ages=[25, 26],
                     cpf_oa_balances=[45000], cash_savings=50000, flat_price=360000)
    fake = FakeMessages([tool_use("assess_household", household), final("Verdict: affordable.")])
    client = NS(messages=fake)

    messages = [{"role": "user", "content": "Can we afford Tengah?"}]
    turn = run_agent(messages, client=client)

    assert turn.text == "Verdict: affordable."
    assert len(turn.tool_calls) == 1 and turn.tool_calls[0].name == "assess_household"
    assert turn.last_assessment["cash"]["verdict"] == "affordable"
    # the tool result was sent back to the model on the second call
    second_call_msgs = fake.calls[1]["messages"]
    assert second_call_msgs[-1]["content"][0]["type"] == "tool_result"


def test_bad_tool_args_go_back_as_errors():
    fake = FakeMessages([tool_use("max_loan", {"flat_price": 360000}), final("Let me fix that.")])
    turn = run_agent([{"role": "user", "content": "hi"}], client=NS(messages=fake))
    assert turn.tool_calls[0].is_error is True
    assert fake.calls[1]["messages"][-1]["content"][0]["is_error"] is True


def test_demo_replay_runs_real_tools_without_api():
    from agent.demo import demo_turn
    household = dict(household_type="family", incomes=[4500, 3500], ages=[25, 26], cpf_oa_balances=[45000],
                      cash_savings=50000, flat_price=0, years_until_key_collection=4)
    turn = demo_turn(household, "tengah-garden-avenue", "4-room")
    assert [c.name for c in turn.tool_calls] == ["list_projects", "get_project_price", "assess_household"]
    assert turn.last_assessment["inputs"]["flat_price"] == 360000   # price came from the tool, not the template
    assert "\\$270,000" in turn.text and "Estimate only" in turn.text


def test_project_household_tool_dispatches():
    request = dict(household_type="family", incomes=[4500, 3500], ages=[25, 26], cpf_oa_balances=[45000],
                   cash_savings=50000, flat_price=360000)
    out, is_error = run_tool("project_household", {"request": request, "years": 2})
    assert not is_error and len(out) == 3
