"""
Pull 5Y income statement / balance sheet / cash flow for a single ticker via
yfinance, normalise to EUR, and cache the result as parquet.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

CACHE_MAX_AGE_HOURS = 24

# yfinance line-item labels used from each statement
INCOME_FIELDS = ["Total Revenue", "EBITDA", "EBIT", "Net Income"]
BALANCE_FIELDS = ["Net Debt", "Total Debt", "Cash And Cash Equivalents", "Stockholders Equity"]


def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker.replace('.', '_')}_financials.parquet"


@lru_cache(maxsize=None)
def fx_rate_to_eur(currency: str) -> tuple[float, str]:
    """
    Return (rate, as_of_date) to convert 1 unit of `currency` into EUR.

    yfinance reports LSE-listed tickers' quote currency as "GBp" (pence),
    but aggregate fields like marketCap are already expressed in GBP, not
    pence — so GBp is treated as GBP here. Only per-share prices need the
    /100 pence-to-pound adjustment, which is handled by callers, not here.
    """
    if currency == "EUR":
        return 1.0, dt.date.today().isoformat()
    if currency == "GBp":
        currency = "GBP"

    pair = f"{currency}EUR=X"
    hist = yf.Ticker(pair).history(period="5d")
    if hist.empty:
        raise ValueError(f"No FX data for {pair}")

    rate = float(hist["Close"].iloc[-1])
    as_of = hist.index[-1].date().isoformat()
    return rate, as_of


@lru_cache(maxsize=None)
def get_info(ticker: str) -> dict:
    return yf.Ticker(ticker).info


def _extract_row(df: pd.DataFrame, label: str) -> pd.Series:
    if df is None or df.empty or label not in df.index:
        return pd.Series(dtype="float64")
    return df.loc[label]


def get_financials(ticker: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Return a tidy DataFrame indexed by fiscal year with both the original
    reporting-currency figures (revenue, ebitda, ebit, net_income, net_debt,
    total_debt, cash, equity) and their EUR-converted counterparts
    (revenue_eur, ebitda_eur, ...), plus currency_original, fx_rate_to_eur,
    fx_date, ticker.

    Original-currency columns match the company's own reported figures 1:1
    (for sanity-checking against public filings). The _eur columns exist
    for one specific purpose: comparables.py needs each peer's market cap
    in a common currency to check it against the eu_midcap_universe's
    EUR 1-10bn screening band. They are NOT needed for multiples (EV/EBITDA,
    P/E, etc.) — those are self-ratios where currency cancels out — nor for
    the football field, which is single-company and can stay in that
    company's own reporting currency throughout.

    Reads from parquet cache in data/cache/ if fresh (< 24h old),
    otherwise pulls from yfinance and re-caches.

    Note: yfinance's free annual statements return ~4 fiscal years, not 5 —
    a Yahoo Finance data limit, not a bug. Rows with no data are dropped.
    """
    cache_file = _cache_path(ticker)

    if not force_refresh and cache_file.exists():
        age_hours = (dt.datetime.now().timestamp() - cache_file.stat().st_mtime) / 3600
        if age_hours < CACHE_MAX_AGE_HOURS:
            return pd.read_parquet(cache_file)

    t = yf.Ticker(ticker)
    info = get_info(ticker)
    # Statements can be in a different currency from the quote (Rockwool:
    # quoted in DKK, reports in EUR), so use financialCurrency here.
    currency = info.get("financialCurrency") or info.get("currency", "EUR")

    income = t.income_stmt
    balance = t.balance_sheet

    if income is None or income.empty:
        raise ValueError(f"yfinance returned no income statement for {ticker}")

    fx_rate, fx_date = fx_rate_to_eur(currency)

    data = {
        "revenue": _extract_row(income, "Total Revenue"),
        "ebitda_reported": _extract_row(income, "EBITDA"),
        "ebitda": _extract_row(income, "Normalized EBITDA"),
        "ebit": _extract_row(income, "EBIT"),
        "net_income": _extract_row(income, "Net Income"),
        "net_debt": _extract_row(balance, "Net Debt"),
        "total_debt": _extract_row(balance, "Total Debt"),
        "cash": _extract_row(balance, "Cash And Cash Equivalents"),
        "equity": _extract_row(balance, "Stockholders Equity"),
    }

    df = pd.DataFrame(data)
    df.index.name = "fiscal_year_end"
    df = df.sort_index()

    # Some issuers have no "Net Debt" line (or it's NaN in the latest year)
    # in yfinance's balance sheet — fall back to total_debt - cash.
    # "ebitda" is Normalized EBITDA (ex one-offs such as impairments); fall
    # back to reported where yfinance has no normalized figure.
    df["ebitda"] = df["ebitda"].fillna(df["ebitda_reported"])

    fallback_net_debt = df["total_debt"] - df["cash"]
    df["net_debt"] = df["net_debt"].fillna(fallback_net_debt)

    # yfinance's free annual statements only cover ~4 fiscal years; older
    # columns come back as an all-NaN placeholder row. Drop them rather than
    # ship fabricated history.
    df = df.dropna(subset=["revenue"])

    # Keep original reporting-currency figures as-is (for verification against
    # public filings) and add parallel EUR columns (for cross-company comps).
    money_cols = ["revenue", "ebitda", "ebitda_reported", "ebit", "net_income", "net_debt", "total_debt", "cash", "equity"]
    for col in money_cols:
        df[f"{col}_eur"] = df[col] * fx_rate

    df["currency_original"] = currency
    df["fx_rate_to_eur"] = fx_rate
    df["fx_date"] = fx_date
    df["ticker"] = ticker

    df.to_parquet(cache_file)
    return df


def get_market_snapshot(ticker: str) -> dict:
    """
    Return current-quote data: price and market_cap in the quote currency,
    market_cap_fin in the financial-statement currency (so EV and P/E never
    mix currencies), market_cap_eur for the EUR 1-10bn screening band, and
    fin_to_quote_per_share to express a per-share value computed from the
    statements in the same units as `price` (handles GBp pence quotes).
    """
    info = get_info(ticker)
    currency = info.get("currency", "EUR")
    financial_currency = info.get("financialCurrency") or currency
    market_cap = info.get("marketCap")

    if market_cap is None:
        raise ValueError(f"yfinance returned no marketCap for {ticker}")

    fx_quote, fx_date = fx_rate_to_eur(currency)
    fx_fin, _ = fx_rate_to_eur(financial_currency)
    pence = 100 if currency == "GBp" else 1

    return {
        "ticker": ticker,
        "company": info.get("shortName") or info.get("longName"),
        "currency": currency,
        "financial_currency": financial_currency,
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "market_cap": market_cap,
        "market_cap_fin": market_cap * fx_quote / fx_fin,
        "market_cap_eur": market_cap * fx_quote,
        "fin_to_quote_per_share": fx_fin / fx_quote * pence,
        "fx_rate_to_eur": fx_quote,
        "fx_date": fx_date,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
    }


if __name__ == "__main__":
    result = get_financials("SIKA.SW")
    print(result)
