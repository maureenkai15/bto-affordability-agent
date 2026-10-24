# BTO Affordability Agent

Purpose: help Singapore adults check if they can afford a BTO flat, using 2026 HDB/CPF rules.

## Rules
- The LLM never does arithmetic. All money maths lives in calculators/ as pure, typed Python functions.
- Every policy number lives in policy_2026.yaml with: value, source_url, as_of / effective_from, verified. No magic numbers in code.
- Every calculator change needs a pytest test with a hand-checked expected value. Run `pytest` before committing.
- Outputs always state assumptions, the policy as-of date, and "estimate only, confirm with your HFE letter".
- Never give financial advice or tell users which flat, bank or product to choose.
- Keep it small: Python 3.11+, anthropic, streamlit, plotly, pyyaml, pytest.

## Layout
- calculators/ — eligibility, grants (EHG), loan (HDB + bank: LTV/MSR/tenure/interest), upfront (stamp duty, option fee), cash (waterfall, payment stages), assess (projects + chains all), projection (CPF/savings over N years)
- agent/ — tools.py (schemas + dispatcher), agent.py (tool-use loop + system prompt), demo.py (free replay, template wording)
- app.py — Streamlit page (calculator and agent demo are free; chat only with a real API key); ui/ — charts, theme, plain-English text; cli.py — terminal chat
- tests/ — unit, test_scenarios.py (8 households), test_projection.py, test_agent_loop.py (fake client + demo), test_app.py (headless app, no API)

## When a new BTO exercise launches
Add its projects from HDB's Annex A (prices, units, waiting time) to policy_2026.yaml `projects`, mark upcoming ones launched, and update tests that pin prices.

## When HDB rules change
1. Edit policy_2026.yaml (value, source_url, date, verified: true).
2. Update the hand-checked test values.
3. Update the policy table in README.md.

## Open items to verify
Values with `verified: false`: legal estimate (HDB's BTO legal fee schedule needed).
