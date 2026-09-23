"""
Multiples-based valuation and football-field assembly.

Applies the peer set's EV/EBITDA and EV/Sales multiples (min/median/max) to
the target company's own EBITDA/Revenue to get a range of implied EVs, then
implied equity value and implied share price. Combines that with the DCF's
sensitivity-matrix range into one football-field data structure.

Everything stays in the target's own reporting currency — see
comparables.py and dcf.py docstrings for why no FX conversion is used here.
"""

from __future__ import annotations

import pandas as pd

from src.core.dcf import run_dcf, sensitivity_matrix
from src.tools.comparables import build_comp_table
from src.tools.financials import get_financials, get_market_snapshot


def multiples_valuation(ticker: str, n_peers: int = 6) -> dict:
    """
    Return implied EV / equity value / share price ranges (low, median, high)
    from applying the peer set's EV/EBITDA and EV/Sales multiples to the
    target's own latest-FY EBITDA and Revenue.
    """
    comp_table = build_comp_table(ticker, n_peers=n_peers)
    peers = comp_table[~comp_table["is_target"]]

    fin = get_financials(ticker)
    latest = fin.iloc[-1]
    target_ebitda = latest["ebitda"]
    target_revenue = latest["revenue"]
    net_debt = latest["net_debt"]

    snap = get_market_snapshot(ticker)
    shares = snap["shares_outstanding"]

    def _implied_range(multiple_col: str, metric: float) -> dict:
        raw_multiples = peers[multiple_col].dropna()
        if raw_multiples.empty or metric is None:
            return {"low": None, "median": None, "high": None}

        # Drop negative or extreme (>3x peer median) multiples so a single
        # distorted denominator can't set the football field's high end.
        median_ref = raw_multiples.median()
        multiples = raw_multiples[(raw_multiples > 0) & (raw_multiples <= 3 * median_ref)]
        if multiples.empty:
            multiples = raw_multiples

        implied_evs = {
            "low": multiples.min() * metric,
            "median": multiples.median() * metric,
            "high": multiples.max() * metric,
        }
        return {
            key: {
                "implied_ev": ev,
                "implied_equity_value": ev - net_debt,
                # Floored at 0: limited liability means equity can't be worth less than nothing.
                "implied_share_price": max(0.0, (ev - net_debt) / shares * snap["fin_to_quote_per_share"]) if shares else None,
            }
            for key, ev in implied_evs.items()
        }

    return {
        "ticker": ticker,
        "currency": snap["currency"],
        "peers_used": peers.index.tolist(),
        "comp_table": comp_table,
        "ev_ebitda": _implied_range("ev_ebitda", target_ebitda),
        "ev_sales": _implied_range("ev_sales", target_revenue),
    }


def build_football_field(ticker: str, sector: str, n_peers: int = 6) -> dict:
    """
    Assemble football-field data: {method: {"low": price, "mid": price, "high": price}}
    for DCF (sensitivity matrix extremes/base), EV/EBITDA multiples, and
    EV/Sales multiples. Prices are per share in the target's quote units.
    Also returns the comp table, DCF base case and sensitivity grid so a UI
    can render everything from one call.
    """
    mult = multiples_valuation(ticker, n_peers=n_peers)
    dcf_base = run_dcf(ticker, sector=sector)
    dcf_grid = sensitivity_matrix(ticker, sector=sector)

    dcf_prices = dcf_grid.values.flatten()
    dcf_prices = dcf_prices[~pd.isna(dcf_prices)]

    football_field = {
        "DCF": {
            "low": float(dcf_prices.min()),
            "mid": dcf_base["implied_share_price"],
            "high": float(dcf_prices.max()),
        },
        "EV/EBITDA": {
            "low": mult["ev_ebitda"]["low"]["implied_share_price"],
            "mid": mult["ev_ebitda"]["median"]["implied_share_price"],
            "high": mult["ev_ebitda"]["high"]["implied_share_price"],
        },
        "EV/Sales": {
            "low": mult["ev_sales"]["low"]["implied_share_price"],
            "mid": mult["ev_sales"]["median"]["implied_share_price"],
            "high": mult["ev_sales"]["high"]["implied_share_price"],
        },
    }

    return {
        "ticker": ticker,
        "currency": mult["currency"],
        "current_price": get_market_snapshot(ticker)["price"],
        "football_field": football_field,
        "comp_table": mult["comp_table"],
        "dcf": dcf_base,
        "sensitivity": dcf_grid,
    }


if __name__ == "__main__":
    import json

    result = build_football_field("SIKA.SW", sector="Materials")
    print(json.dumps(result["football_field"], indent=2, default=float))
