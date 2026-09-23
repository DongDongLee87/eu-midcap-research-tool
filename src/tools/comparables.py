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
    Return up to `n` peer tickers for `ticker` from the same sector in the
    universe CSV, market cap inside the EUR 1-10bn band, excluding `ticker`.
    Same hand-tagged peer_group ranks first (so Sika gets chemicals, not
    steel/copper/cement); remaining slots are filled from the wider sector.
    Within each tier, ranked by market-cap proximity.

    `ticker` itself is exempt from the band (Sika is a large-cap).
    """
    universe = load_universe()
    if ticker not in universe["ticker"].values:
        raise ValueError(f"{ticker} is not in the universe CSV — add it first")

    target = universe.loc[universe["ticker"] == ticker].iloc[0]
    candidates = universe[(universe["sector"] == target["sector"]) & (universe["ticker"] != ticker)]

    target_cap_eur = get_market_snapshot(ticker)["market_cap_eur"]

    scored = []
    for _, row in candidates.iterrows():
        peer = row["ticker"]
        try:
            snap = get_market_snapshot(peer)
        except ValueError:
            continue
        cap_eur = snap["market_cap_eur"]
        if not (MIN_MARKET_CAP_EUR <= cap_eur <= MAX_MARKET_CAP_EUR):
            continue
        if not _has_usable_financials(peer):
            continue
        tier = 0 if row["peer_group"] == target["peer_group"] else 1
        scored.append((peer, tier, abs(cap_eur - target_cap_eur)))

    scored.sort(key=lambda x: (x[1], x[2]))
    return [peer for peer, _, _ in scored[:n]]


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

    market_cap = snap["market_cap_fin"]
    net_debt = fy["net_debt"]
    ebitda = fy["ebitda"]
    revenue = fy["revenue"]
    net_income = fy["net_income"]
    equity = fy["equity"]

    ev = market_cap + net_debt

    return {
        "ticker": ticker,
        "company": snap["company"],
        "currency": snap["financial_currency"],
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
