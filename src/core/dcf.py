"""
Simplified 5-year DCF with a WACC x terminal-growth sensitivity matrix.

Deliberately simple: flat EBITDA margin, flat D&A/CapEx/NWC ratios, WACC and
terminal growth from a hand-set sector lookup rather than a live CAPM/beta
calculation. This is a portfolio-piece DCF meant to demonstrate mechanics
and judgement, not to replace an analyst's own model — see CLAUDE.md §2
"deliberate product boundaries".

Everything stays in the target company's own reporting currency (no FX
conversion needed for a single-company valuation — see financials.py).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from src.tools.financials import get_financials, get_market_snapshot

WACC_PATH = Path(__file__).resolve().parents[2] / "data" / "reference" / "sector_wacc.json"

DEFAULT_TAX_RATE = 0.25
FORECAST_YEARS = 5


def load_sector_assumptions(sector: str) -> dict:
    with open(WACC_PATH) as f:
        table = json.load(f)
    if sector not in table:
        raise ValueError(f"No WACC assumptions for sector '{sector}' in {WACC_PATH}")
    return table[sector]


def _cashflow_ratios(ticker: str) -> dict:
    """Latest-FY D&A and CapEx as a fraction of revenue, from the cash flow statement."""
    cf = yf.Ticker(ticker).cashflow
    fin = get_financials(ticker)
    revenue = fin.iloc[-1]["revenue"]

    da = cf.loc["Depreciation And Amortization"].dropna().iloc[0] if "Depreciation And Amortization" in cf.index else None
    capex = cf.loc["Capital Expenditure"].dropna().iloc[0] if "Capital Expenditure" in cf.index else None

    if da is None or capex is None:
        raise ValueError(f"Missing D&A or CapEx in cash flow statement for {ticker}")

    return {
        "da_pct_revenue": da / revenue,
        "capex_pct_revenue": abs(capex) / revenue,
    }


def _effective_tax_rate(ticker: str) -> float:
    inc = yf.Ticker(ticker).income_stmt
    if "Tax Provision" not in inc.index or "Pretax Income" not in inc.index:
        return DEFAULT_TAX_RATE

    tax = inc.loc["Tax Provision"].dropna()
    pretax = inc.loc["Pretax Income"].dropna()
    if tax.empty or pretax.empty or pretax.iloc[0] == 0:
        return DEFAULT_TAX_RATE

    rate = tax.iloc[0] / pretax.iloc[0]
    return rate if 0.05 <= rate <= 0.40 else DEFAULT_TAX_RATE


def _historical_revenue_cagr(revenue: pd.Series) -> float:
    revenue = revenue.dropna()
    if len(revenue) < 2:
        return 0.0
    n_periods = len(revenue) - 1
    return (revenue.iloc[-1] / revenue.iloc[0]) ** (1 / n_periods) - 1


def _working_capital_pct_revenue(ticker: str, revenue: float) -> float:
    bs = yf.Ticker(ticker).balance_sheet
    if "Working Capital" not in bs.index:
        return 0.0
    wc = bs.loc["Working Capital"].dropna()
    if wc.empty:
        return 0.0
    return wc.iloc[0] / revenue


def build_assumptions(ticker: str, sector: str) -> dict:
    """Assemble every input the DCF needs, all derived from historical financials."""
    fin = get_financials(ticker)
    latest = fin.iloc[-1]

    sector_assumptions = load_sector_assumptions(sector)
    cf_ratios = _cashflow_ratios(ticker)

    return {
        "revenue_latest": latest["revenue"],
        "ebitda_margin": latest["ebitda"] / latest["revenue"],
        "revenue_growth_start": _historical_revenue_cagr(fin["revenue"]),
        "terminal_growth": sector_assumptions["terminal_growth"],
        "wacc": sector_assumptions["wacc"],
        "tax_rate": _effective_tax_rate(ticker),
        "da_pct_revenue": cf_ratios["da_pct_revenue"],
        "capex_pct_revenue": cf_ratios["capex_pct_revenue"],
        "nwc_pct_revenue": _working_capital_pct_revenue(ticker, latest["revenue"]),
        "net_debt": latest["net_debt"],
    }


def forecast_free_cash_flows(assumptions: dict, wacc: float, terminal_growth: float) -> list[float]:
    """Project FORECAST_YEARS of unlevered FCF. Revenue growth decays linearly
    from the historical CAGR to the terminal growth rate by the final year."""
    revenue = assumptions["revenue_latest"]
    g_start = assumptions["revenue_growth_start"]
    g_end = terminal_growth
    margin = assumptions["ebitda_margin"]
    da_pct = assumptions["da_pct_revenue"]
    capex_pct = assumptions["capex_pct_revenue"]
    nwc_pct = assumptions["nwc_pct_revenue"]
    tax_rate = assumptions["tax_rate"]

    fcfs = []
    prev_revenue = revenue
    for year in range(1, FORECAST_YEARS + 1):
        g = g_start + (g_end - g_start) * (year - 1) / (FORECAST_YEARS - 1) if FORECAST_YEARS > 1 else g_end
        rev_t = prev_revenue * (1 + g)

        ebitda_t = rev_t * margin
        da_t = rev_t * da_pct
        ebit_t = ebitda_t - da_t
        nopat_t = ebit_t * (1 - tax_rate)

        capex_t = rev_t * capex_pct
        delta_nwc_t = nwc_pct * (rev_t - prev_revenue)

        fcf_t = nopat_t + da_t - capex_t - delta_nwc_t
        fcfs.append(fcf_t)
        prev_revenue = rev_t

    return fcfs


def discount_fcfs(fcfs: list[float], wacc: float, terminal_growth: float) -> dict:
    pv_fcfs = [fcf / (1 + wacc) ** (i + 1) for i, fcf in enumerate(fcfs)]
    terminal_value = fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    pv_terminal_value = terminal_value / (1 + wacc) ** len(fcfs)

    enterprise_value = sum(pv_fcfs) + pv_terminal_value
    return {
        "pv_fcfs": pv_fcfs,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
    }


def run_dcf(ticker: str, sector: str) -> dict:
    """
    Run the full simplified DCF for `ticker` and return enterprise value,
    implied equity value, implied share price, and the assumptions used.
    """
    assumptions = build_assumptions(ticker, sector)

    wacc = assumptions["wacc"]
    terminal_growth = assumptions["terminal_growth"]

    if wacc <= terminal_growth:
        raise ValueError(f"WACC ({wacc:.1%}) must exceed terminal growth ({terminal_growth:.1%})")

    fcfs = forecast_free_cash_flows(assumptions, wacc, terminal_growth)
    result = discount_fcfs(fcfs, wacc, terminal_growth)

    snap = get_market_snapshot(ticker)

    equity_value = result["enterprise_value"] - assumptions["net_debt"]
    shares = snap["shares_outstanding"]
    implied_share_price = equity_value / shares if shares else None

    return {
        "ticker": ticker,
        "assumptions": assumptions,
        "fcfs": fcfs,
        "enterprise_value": result["enterprise_value"],
        "equity_value": equity_value,
        "implied_share_price": implied_share_price,
        "shares_outstanding": shares,
        "currency": snap["currency"],
    }


def sensitivity_matrix(
    ticker: str,
    sector: str,
    wacc_range: list[float] | None = None,
    growth_range: list[float] | None = None,
) -> pd.DataFrame:
    """
    Return a DataFrame of implied share price, rows = WACC, columns =
    terminal growth, holding all other assumptions fixed at their base case.
    """
    assumptions = build_assumptions(ticker, sector)

    snap = get_market_snapshot(ticker)
    shares = snap["shares_outstanding"]
    net_debt = assumptions["net_debt"]

    base_wacc = assumptions["wacc"]
    base_g = assumptions["terminal_growth"]

    if wacc_range is None:
        wacc_range = [round(base_wacc + delta, 4) for delta in (-0.01, -0.005, 0, 0.005, 0.01)]
    if growth_range is None:
        growth_range = [round(base_g + delta, 4) for delta in (-0.01, -0.005, 0, 0.005, 0.01)]

    grid = pd.DataFrame(index=[f"{w:.2%}" for w in wacc_range], columns=[f"{g:.2%}" for g in growth_range], dtype=float)

    for w in wacc_range:
        for g in growth_range:
            if w <= g:
                grid.loc[f"{w:.2%}", f"{g:.2%}"] = np.nan
                continue
            fcfs = forecast_free_cash_flows(assumptions, w, g)
            result = discount_fcfs(fcfs, w, g)
            equity_value = result["enterprise_value"] - net_debt
            price = equity_value / shares if shares else np.nan
            grid.loc[f"{w:.2%}", f"{g:.2%}"] = price

    grid.index.name = "WACC"
    grid.columns.name = "Terminal Growth"
    return grid


if __name__ == "__main__":
    pd.set_option("display.width", 200)

    dcf_result = run_dcf("SIKA.SW", sector="Materials")
    print("=== DCF base case ===")
    print(f"Enterprise value: {dcf_result['enterprise_value']:,.0f} {dcf_result['currency']}")
    print(f"Equity value:     {dcf_result['equity_value']:,.0f} {dcf_result['currency']}")
    print(f"Implied price:    {dcf_result['implied_share_price']:.2f} {dcf_result['currency']}")
    print()
    print("Assumptions:", dcf_result["assumptions"])
    print()
    print("=== Sensitivity matrix (implied share price) ===")
    print(sensitivity_matrix("SIKA.SW", sector="Materials"))
