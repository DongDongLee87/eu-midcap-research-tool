"""
Build a comparables (comp) table for a ticker: pick peers from the
hand-curated eu_midcap_universe.csv (see CLAUDE.md Trap 2 — no automated
sector/size screening) and compute valuation multiples.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.tools.financials import get_financials, get_market_snapshot

UNIVERSE_PATH = Path(__file__).resolve().parents[2] / "data" / "reference" / "eu_midcap_universe.csv"

MIN_MARKET_CAP_EUR = 1e9
MAX_MARKET_CAP_EUR = 10e9


def load_universe() -> pd.DataFrame:
    return pd.read_csv(UNIVERSE_PATH)


def select_peers(ticker: str, n: int = 6) -> list[str]:
    """
    Return up to `n` peer tickers for `ticker`: same sector tag in the
    universe CSV, market cap inside the EUR 1-10bn screening band, excluding
    `ticker` itself, ranked by market-cap proximity to `ticker`'s own cap.

    `ticker` does not need to itself be inside the 1-10bn band (the target
    company may be a large-cap, as Sika is) — only candidate peers are
    screened against the band.
    """
    universe = load_universe()
    if ticker not in universe["ticker"].values:
        raise ValueError(f"{ticker} is not in the universe CSV — add it first")

    sector = universe.loc[universe["ticker"] == ticker, "sector"].iloc[0]
    candidates = universe[(universe["sector"] == sector) & (universe["ticker"] != ticker)]["ticker"].tolist()

    target_cap_eur = get_market_snapshot(ticker)["market_cap_eur"]

    scored = []
    for peer in candidates:
        try:
            snap = get_market_snapshot(peer)
        except ValueError:
            continue
        cap_eur = snap["market_cap_eur"]
        if not (MIN_MARKET_CAP_EUR <= cap_eur <= MAX_MARKET_CAP_EUR):
            continue
        if not _has_usable_financials(peer):
            continue
        scored.append((peer, abs(cap_eur - target_cap_eur)))

    scored.sort(key=lambda x: x[1])
    return [peer for peer, _ in scored[:n]]


def _has_usable_financials(ticker: str) -> bool:
    """True if the latest fiscal year has enough data to compute EV-based multiples."""
    try:
        fy = _latest_fy(ticker)
    except (ValueError, IndexError):
        return False
    return pd.notna(fy["ebitda"]) and pd.notna(fy["revenue"]) and pd.notna(fy["net_debt"])


def _latest_fy(ticker: str) -> pd.Series:
    df = get_financials(ticker)
    return df.iloc[-1]


def _company_row(ticker: str) -> dict:
    snap = get_market_snapshot(ticker)
    fy = _latest_fy(ticker)

    market_cap = snap["market_cap"]
    net_debt = fy["net_debt"]
    ebitda = fy["ebitda"]
    revenue = fy["revenue"]
    net_income = fy["net_income"]
    equity = fy["equity"]

    ev = market_cap + net_debt

    return {
        "ticker": ticker,
        "company": snap["company"],
        "currency": snap["currency"],
        "fiscal_year_end": fy.name,
        "market_cap": market_cap,
        "ev": ev,
        "ev_ebitda": ev / ebitda if ebitda else None,
        "ev_sales": ev / revenue if revenue else None,
        "pe": market_cap / net_income if net_income else None,
        "roe": net_income / equity if equity else None,
        "net_debt_ebitda": net_debt / ebitda if ebitda else None,
    }


def build_comp_table(ticker: str, n_peers: int = 6) -> pd.DataFrame:
    """
    Return a DataFrame with one row for `ticker` and up to `n_peers` rows
    for its peers (target row is not marked as a peer). Multiples are
    computed per-company in that company's own reporting currency — see
    financials.py docstring for why no FX conversion is needed here.
    """
    peers = select_peers(ticker, n=n_peers)
    tickers = [ticker] + peers

    rows = [_company_row(t) for t in tickers]
    df = pd.DataFrame(rows).set_index("ticker")
    df["is_target"] = df.index == ticker
    return df


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    table = build_comp_table("SIKA.SW")
    print(table)
