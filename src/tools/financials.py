"""
Pull 5Y income statement / balance sheet / cash flow for a single ticker via
yfinance, normalise to EUR, and cache the result as parquet.
"""

from __future__ import annotations

import datetime as dt
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


def _fx_rate_to_eur(currency: str) -> tuple[float, str]:
    """Return (rate, as_of_date) to convert 1 unit of `currency` into EUR."""
    if currency == "EUR":
        return 1.0, dt.date.today().isoformat()

    pair = f"{currency}EUR=X"
    hist = yf.Ticker(pair).history(period="5d")
    if hist.empty:
        raise ValueError(f"No FX data for {pair}")

    rate = float(hist["Close"].iloc[-1])
    as_of = hist.index[-1].date().isoformat()
    return rate, as_of


def _extract_row(df: pd.DataFrame, label: str) -> pd.Series:
    if df is None or df.empty or label not in df.index:
        return pd.Series(dtype="float64")
    return df.loc[label]


def get_financials(ticker: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Return a tidy DataFrame indexed by fiscal year with columns:
    revenue, ebitda, ebit, net_income, net_debt, total_debt, cash,
    equity (all in EUR), plus currency, fx_rate, fx_date, fiscal_year_end.

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
    info = t.info
    currency = info.get("currency", "EUR")

    income = t.income_stmt
    balance = t.balance_sheet

    if income is None or income.empty:
        raise ValueError(f"yfinance returned no income statement for {ticker}")

    fx_rate, fx_date = _fx_rate_to_eur(currency)

    data = {
        "revenue": _extract_row(income, "Total Revenue"),
        "ebitda": _extract_row(income, "EBITDA"),
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

    # yfinance's free annual statements only cover ~4 fiscal years; older
    # columns come back as an all-NaN placeholder row. Drop them rather than
    # ship fabricated history.
    df = df.dropna(subset=["revenue"])

    # Convert all monetary columns to EUR
    money_cols = ["revenue", "ebitda", "ebit", "net_income", "net_debt", "total_debt", "cash", "equity"]
    for col in money_cols:
        df[col] = df[col] * fx_rate

    df["currency_original"] = currency
    df["fx_rate_to_eur"] = fx_rate
    df["fx_date"] = fx_date
    df["ticker"] = ticker

    df.to_parquet(cache_file)
    return df


if __name__ == "__main__":
    result = get_financials("SIKA.SW")
    print(result)
