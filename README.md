# 🏠 BTO Affordability Agent

**"Can we afford a 4-room BTO in Tengah?"** An AI agent that answers this for any Singapore household, using 2026 HDB and CPF rules, and shows exactly where every number comes from.

<!-- Replace with your demo GIF: record a 30-second run of one example question -->
![Demo](docs/demo.gif)

**Live app:** _add your Streamlit Cloud link here_

## Why I built this

Most couples in their 20s piece this question together from HDB pages, CPF pages and blog posts. Each source covers one piece: grants, loan limits or prices. None of them shows the whole picture for *your* incomes and savings, and many blogs are still out of date (the 80% LTV and the $14,000 income ceiling no longer apply).

## Two modes

| Mode | Needs | Cost |
| --- | --- | --- |
| **Form** (default) | nothing | free: runs the Python calculators directly |
| **Chat** | an Anthropic API key in `.env` or Streamlit Secrets | paid per token (Claude Pro does not cover the API) |

Both modes use the same calculators and the same breakdown panel. Without a key, chat mode is switched off and the app never calls the API, so the public demo costs nothing.

## How it works

```mermaid
flowchart LR
    U["You ask<br/>'Can we afford Tengah?'"] --> A["Claude agent<br/>asks for missing inputs<br/>picks tools, loops<br/>never does maths"]
    A -- calls --> T
    T -- results --> A
    subgraph T["Python calculators (pytest-tested)"]
        T1[get_project_price]
        T2[check_eligibility]
        T3[get_ehg_grant]
        T4[max_loan]
        T5[upfront_costs]
        T6[cash_gap]
        T7[assess_household]
    end
    P[("policy_2026.yaml<br/>value + source + as-of")] --> T
    A --> R["Answer<br/>verdict, numbers table,<br/>assumptions, what to confirm"]
```

**The design choice:** the LLM never does arithmetic. It decides which calculator to call and explains the result. All money maths lives in small, typed, tested Python functions, and every policy number lives in one dated YAML file with a source link. A rule change is a one-line edit.

## How the numbers are computed

1. **Eligibility:** combined gross monthly income ≤ $16,000 for families (≤ $8,000 for singles aged 35+).
2. **Grant:** Enhanced CPF Housing Grant from HDB's 16-band income table, up to $120,000.
3. **HDB loan:** the smallest of three limits:
   - 75% of the flat price (LTV)
   - the loan whose instalment is 30% of gross income (MSR), sized at HDB's 3.0% interest rate floor
   - price minus grants (what you actually need)

   Tenure is the shorter of 25 years and 65 minus the applicants' average age at key collection.
4. **Instalment:** standard annuity formula at the actual 2.6% p.a. (so an MSR-bound loan uses about 29% of income, not 30%)

   `instalment = L × r / (1 − (1 + r)^−n)`, where `r = 2.6% / 12` and `n = 12 × tenure`

5. **Cash gap:** price − grant − loan = downpayment. CPF OA pays first, then cash, plus upfront costs (option fee, stamp duty, legal). The verdict is **tight** if you'd have under 6 months of instalments left in cash.

## Policy values (as of 24 Oct 2026)

| Rule | Value | Source |
| --- | --- | --- |
| Income ceiling, families | $16,000/month (from 24 Aug 2026) | [PropertyNet](https://propertynet.sg/ndr-2026-bto-income-ceiling-16000-ec-18000-extra-ballot-chances/) |
| Income ceiling, singles 35+ | $8,000/month | same |
| EHG, families | up to $120,000, ceiling $9,000 | [gov.sg](https://www.togetherforbetter.gov.sg/lifestage/youngadults/) |
| HDB loan rate | 2.6% p.a. | [EdgeProp](https://www.edgeprop.sg/property-news/guide-hdb-concessionary-housing-loan) |
| LTV / MSR | 75% / 30% | [ShopBack](https://www.shopback.sg/blog/finance/hdb-vs-bank-loan), confirmed on HDB "Housing Loan from HDB" |
| Loan assessment rate floor | 3.0% (loan sized at the higher of this and 2.6%) | [HDB press release](https://www.hdb.gov.sg/about-us/news-and-publications/press-releases/29092022-propertymeasures2022) |
| Loan tenure | shortest of 25 years and 65 minus average age | HDB "Housing Loan from HDB" (updated 23 Aug 2026) |
| Tengah Garden Ave 4-room | ~$360k–$380k indicative (Nov 2026 exercise) | [SG Property Index](https://sgpropertyindex.com/launches/bto/tengah-garden-avenue/) |

Values marked `verified: false` in `policy_2026.yaml` (singles EHG bands, stamp duty tiers, option fee, legal estimate) are shown as warnings in the app until confirmed on hdb.gov.sg and iras.gov.sg.

## Tested scenarios

`tests/test_scenarios.py` covers eight real households: a typical dual-income couple, a couple just above the $9,000 grant cliff, a couple eligible only under the new $16,000 ceiling, a couple above it, a single-income household where the 30% MSR binds, a single aged 35+, a citizen + PR couple, and low-CPF vs high-CPF households. Plus an older buyer whose loan tenure shrinks while waiting for keys.

`tests/test_app.py` runs the Streamlit app headlessly in form mode with the 3 sidebar examples (hand-checked numbers) and asserts the API client is never created.

```
60 passed
```

## Run it

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                             # 60 tests, no API key needed
streamlit run app.py               # web app, free form mode

# Optional, paid: chat mode
cp .env.example .env               # then paste your Anthropic API key
python cli.py                      # chat in the terminal (or use Chat mode in the app)
```

## Project structure

```
bto-agent/
├── app.py                 Streamlit UI: form or chat + waterfall chart + MSR bar + tool-call log
├── cli.py                 Terminal version
├── policy_2026.yaml       Every policy number, with source and as-of date
├── agent/
│   ├── agent.py           Tool-use loop (Anthropic SDK)
│   └── tools.py           Tool schemas + dispatcher
├── calculators/           Pure functions, no LLM
│   ├── eligibility.py  grants.py  loan.py  upfront.py  cash.py
│   ├── assess.py          Chains them for a full assessment
│   └── policy.py          Loads the YAML, flags stale/unverified values
└── tests/                 Unit tests, 8 household scenarios, agent loop with a fake client, app in form mode
```

## Limitations

- Prices for the November 2026 exercise are indicative until HDB publishes them at launch.
- Assumes first-timers and that current income equals the 12-month average HDB uses.
- Does not model the Proximity Housing Grant (resale only), resale flats, bank loans or ECs.
- Downpayment staging (signing vs key collection) is not modelled; the tool shows the total.

**Estimate only. Your HDB Flat Eligibility (HFE) letter is the official answer. Not financial advice.**
