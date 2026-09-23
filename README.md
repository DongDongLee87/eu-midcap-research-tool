# EU Mid-Cap Valuation Tool

![Football field for Sika AG](docs/screenshots/01_football_field.png)

**Live demo:** https://eu-midcap-research-tool.streamlit.app  (enter `SIKA.SW`; first load takes ~30 s)

Enter a European Industrials/Materials ticker and the tool builds a peer set from a hand-curated universe, computes a comparables table, runs a simplified DCF with a WACC × terminal-growth sensitivity grid, and plots all three valuation methods on a football-field chart. It automates the data plumbing of an equity initiation so the analyst's time goes into judgement, not spreadsheets.

## Why I built it

As a Swiss finalist in the CFA Research Challenge 2025 (Industrials/Materials), I saw how much of an initiation report's time goes into pulling statements, normalising currencies and rebuilding the same comp table, rather than into the thesis itself. This project takes that workflow — financials → peer set → multiples → DCF → football field — and turns it into a reproducible pipeline, so every number can be traced back to its source and its assumptions.

## Architecture

A deterministic pipeline: four small modules, one UI. No LLM, no agent loop (see [design decisions](#validation-and-design-decisions)).

```
app.py                       Streamlit UI: ticker input, football field, comp table, DCF detail
│
└── src/tools/valuation.py   Football-field assembly: applies peer multiples, merges DCF range
    ├── src/tools/comparables.py   Peer selection from the curated universe, multiples per company
    ├── src/core/dcf.py            5-year unlevered FCF, terminal value, sensitivity grid
    └── src/tools/financials.py    yfinance data layer: statements, quotes, FX, parquet cache

data/reference/eu_midcap_universe.csv   33 hand-tagged tickers (sector, sub-sector, peer group)
data/reference/sector_wacc.json          hand-set WACC / terminal growth per sector
```

The case study [`case_studies/sika_initiation.md`](case_studies/sika_initiation.md) walks through one full run end to end.

## What it deliberately doesn't do

These are scope decisions, not missing features:

- **No buy / sell / hold recommendation.** The output is an input to analyst judgement, not a substitute for it.
- **No automated thesis generation.** The tool shows where methods agree and disagree; explaining why is the analyst's job.
- **No Bloomberg-grade consensus data.** It uses Yahoo Finance via `yfinance` as a disclosed, free proxy.
- **No coverage below €500m market cap.** Public data quality degrades sharply for small caps.
- **No automated sector screening for peers.** The universe is curated by hand (see below).

## Validation and design decisions

**Why there is no AI agent.** The first design borrowed an agent loop (ReAct-style planning + scratchpad) from [`virattt/dexter`](https://github.com/virattt/dexter). I removed it. A valuation workflow is deterministic: statements → peers → multiples → DCF. There is no branching decision for a language model to make, so an agent layer would only add latency and the risk of hallucinated numbers, with no analytical benefit. Every output here is reproducible from the same inputs.

**Hand-curated universe instead of automated screening.** Yahoo's industry labels for European mid-caps are unreliable, so peers come from a 33-name CSV tagged by hand with sector, sub-sector and peer group. Peers from the target's own peer group rank first, then candidates from the wider sector fill any remaining slots; within each tier, peers are ranked by market-cap proximity and must fall in the €1–10bn band. An early version matched on sector alone and gave Sika (construction chemicals) a steel producer, a copper smelter and a cement maker as peers — technically "Materials", analytically useless. The peer-group tag fixed that.

**Currency handling — ratios never mix currencies.** Multiples are computed in each company's own statement currency, where currency cancels out; EUR conversion is used only to screen peers against the €1–10bn band. Two traps were found and fixed:
- *Quote currency ≠ reporting currency.* Rockwool is quoted in DKK but reports in EUR. Dividing a DKK market cap by EUR EBITDA produced a 78.8× EV/EBITDA. Market cap is now converted into the statement currency (`financialCurrency`) before computing EV; Rockwool's multiple is 10.8× reported / 5.9× normalized.
- *Pence.* LSE stocks are quoted in GBp while market cap is in GBP; implied per-share values are converted back to pence for UK names.

**Normalized EBITDA.** Reported EBITDA for several names was distorted by one-offs such as impairments: normalized was +82% for Rockwool, +70% for Lanxess and +58% for Croda. On reported numbers, Croda looked like a 19.8× "premium" name; normalized it is 12.5×. All multiples and the DCF margin use normalized EBITDA, falling back to reported where it is missing.

**Net debt includes lease liabilities.** Yahoo's "Net Debt" line leaves out IFRS 16 lease liabilities, but IFRS 16 EBITDA already excludes lease costs. Using Yahoo's line would therefore understate every company's EV relative to its EBITDA. The tool computes net debt as total debt (including leases) minus cash. This issue came to light during manual verification (below).

**Other data guards.**
- Peer multiples above 3× the peer median are excluded from the football-field range.
- Implied equity values are floored at zero (limited liability).
- Peers with incomplete statements are skipped rather than patched; for example, Fuchs has no debt data for its latest year, so the next eligible peer is used instead.
- `yfinance` returns only ~4 fiscal years of annual data, not 5. Empty years are dropped, not filled.

**Manual verification against the annual report.** I checked the tool's FY2025 figures for Sika against the Sika Annual Report 2025:

| Item (CHF m) | Tool | Annual report | Result |
|---|---:|---:|---|
| Net sales | 11,201.3 | 11,201.3 | Exact match |
| Net profit | 1,044.0 | 1,045.3 | Definitional: the tool uses profit attributable to shareholders (the correct P/E numerator); the report figure includes CHF 1.3m of minority interests |
| Net debt | 4,716.2 | 4,734.5 | Within 0.4%, after the fix; before it, Yahoo's figure was 4,278.0 (−10%), because it excluded leases |
| Net debt / EBITDA | 2.26× | 2.3× | Consistent |

The net-debt check is what exposed the lease issue described above.

**Testing.** Smoke-tested end to end, both locally and on the deployed app from a logged-out browser. The tests cover SIKA.SW (CHF), WEIR.L (GBp) and ROCK-B.CO (DKK quote / EUR statements), each chosen to exercise a different currency case.

## Honest limitations

- **Not battle-tested.** Smoke checks only, no test suite. It is a portfolio prototype, not production software.
- **yfinance is not Bloomberg.** Yahoo data can be late, restated or wrong, and the unofficial API can break or rate-limit without warning. "Normalized EBITDA" follows Yahoo's definition, not the company's own adjusted figures.
- **The demo company is outside the tool's own universe.** Sika's market cap (~CHF 30bn) is well above the €1–10bn band. It was chosen for recognisability, and it has no true peer among European chemical mid-caps, which currently trade at trough multiples. The multiples bars in the case study are therefore informative about *how differently* Sika is priced, not about its fair value.
- **EV/Sales is kept but flawed for high-margin targets.** Applying low-margin peers' EV/Sales multiples to Sika (EBITDA margin ~19%) systematically undervalues it. Choosing which metrics fit which company is left to the analyst.
- **The DCF is deliberately simple.** Margins and D&A/CapEx/working-capital ratios are held flat at latest-year levels. Revenue growth decays linearly from the historical CAGR (only 3 years of history) to terminal growth. WACC and terminal growth are hand-set per sector rather than derived from CAPM.
- **Latest fiscal year only.** No TTM or forward (NTM) figures, so multiples will differ from terminals that default to TTM/NTM.
- **FX is a single spot snapshot** taken at load time.

## Running locally

Requires Python 3.12 (the pinned pandas/numpy/pyarrow versions have no wheels for 3.14).

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Attribution

See [ATTRIBUTION.md](ATTRIBUTION.md).
