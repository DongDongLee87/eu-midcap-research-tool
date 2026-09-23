"""EU Mid-Cap Research Tool — single-page Streamlit UI."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.tools.comparables import load_universe
from src.tools.financials import fx_rate_to_eur, get_info
from src.tools.valuation import build_football_field

BAR_COLOR = "#2a78d6"
INK = "#52514e"

st.set_page_config(page_title="EU Mid-Cap Valuation", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def run_pipeline(ticker: str, sector: str) -> dict:
    # Per-process yfinance caches would otherwise never expire.
    get_info.cache_clear()
    fx_rate_to_eur.cache_clear()
    return build_football_field(ticker, sector=sector)


def football_field_chart(ff: dict, current_price: float, currency: str) -> go.Figure:
    methods = list(ff.keys())[::-1]
    lows = [ff[m]["low"] for m in methods]
    highs = [ff[m]["high"] for m in methods]
    mids = [ff[m]["mid"] for m in methods]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=methods,
        x=[h - l for l, h in zip(lows, highs)],
        base=lows,
        orientation="h",
        marker=dict(color=BAR_COLOR, cornerradius=4),
        width=0.45,
        customdata=list(zip(lows, mids, highs)),
        hovertemplate=(
            "<b>%{y}</b><br>Low: %{customdata[0]:,.1f}<br>"
            "Mid: %{customdata[1]:,.1f}<br>High: %{customdata[2]:,.1f}<extra></extra>"
        ),
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        y=methods,
        x=mids,
        mode="markers",
        marker=dict(symbol="line-ns", size=22, line=dict(width=3, color="white")),
        hoverinfo="skip",
        showlegend=False,
    ))
    fig.add_vline(
        x=current_price,
        line=dict(color=INK, width=2, dash="dash"),
        annotation_text=f"Current {current_price:,.1f}",
        annotation_position="top",
    )
    fig.update_layout(
        xaxis_title=f"Implied value per share ({currency})",
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        bargap=0.4,
    )
    fig.update_xaxes(rangemode="tozero", gridcolor="rgba(128,128,128,0.15)")
    fig.update_yaxes(showgrid=False)
    return fig


def format_comp_table(comp: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    df = comp.copy()
    df["company"] = df.index.map(universe.set_index("ticker")["company"])
    # Negative earnings make P/E meaningless; show n.m. rather than a negative multiple.
    df.loc[df["pe"] < 0, "pe"] = float("nan")
    df["market_cap"] = df["market_cap"] / 1e9
    df["ev"] = df["ev"] / 1e9
    df["roe"] = df["roe"] * 100
    df = df.rename(columns={
        "company": "Company",
        "currency": "Ccy",
        "market_cap": "Mkt cap (bn)",
        "ev": "EV (bn)",
        "ev_ebitda": "EV/EBITDA",
        "ev_sales": "EV/Sales",
        "pe": "P/E",
        "roe": "ROE %",
        "net_debt_ebitda": "ND/EBITDA",
    })
    cols = ["Company", "Ccy", "Mkt cap (bn)", "EV (bn)", "EV/EBITDA", "EV/Sales", "P/E", "ROE %", "ND/EBITDA"]
    return df[cols]


st.title("EU Mid-Cap Valuation")
st.caption(
    "Enter a ticker from the curated European Industrials/Materials universe to get "
    "a comparables table and a football-field valuation (DCF + peer multiples)."
)

universe = load_universe()

with st.form("ticker_form"):
    ticker = st.text_input("Ticker", value="SIKA.SW").strip().upper()
    submitted = st.form_submit_button("Run valuation")

with st.expander(f"Available tickers ({len(universe)})"):
    st.dataframe(
        universe[["ticker", "company", "country", "sector", "peer_group"]],
        hide_index=True,
        use_container_width=True,
    )

if ticker not in universe["ticker"].values:
    st.error(f"{ticker} is not in the curated universe. Pick one from the list above.")
    st.stop()

sector = universe.loc[universe["ticker"] == ticker, "sector"].iloc[0]

with st.spinner(f"Pulling data for {ticker} and its peers (first run ~30s)..."):
    try:
        result = run_pipeline(ticker, sector)
    except Exception as e:
        st.error(f"Data retrieval failed: {e}. Yahoo Finance may be rate-limiting — try again in a minute.")
        st.stop()

currency = result["currency"]
dcf = result["dcf"]

c1, c2, c3 = st.columns(3)
c1.metric("Current price", f"{result['current_price']:,.2f} {currency}")
c2.metric("DCF implied (base)", f"{dcf['implied_share_price']:,.2f} {currency}")
c3.metric("Peers", len(result["comp_table"]) - 1)

st.subheader("Football field")
st.plotly_chart(
    football_field_chart(result["football_field"], result["current_price"], currency),
    use_container_width=True,
)
st.caption(
    "Bars span low–high; white tick = mid. DCF range = WACC ±1pp × terminal growth ±1pp. "
    "Multiples range = peer min / median / max (multiples >3× peer median excluded). "
    "Implied values floored at 0."
)

st.subheader("Comparables")
st.dataframe(
    format_comp_table(result["comp_table"], universe).style.format(precision=2, na_rep="n.m."),
    use_container_width=True,
)
st.caption(
    "Latest fiscal year, normalized EBITDA (ex one-offs), EV = market cap + net debt. Each row in the "
    "company's own reporting currency — ratios need no FX conversion."
)

with st.expander("DCF sensitivity (implied price per share)"):
    st.dataframe(result["sensitivity"].style.format(precision=1), use_container_width=True)

with st.expander("DCF assumptions"):
    a = dcf["assumptions"]
    st.table(pd.DataFrame({
        "Assumption": [
            "WACC", "Terminal growth", "Revenue growth (yr 1, historical CAGR)",
            "EBITDA margin", "Tax rate", "D&A % revenue", "CapEx % revenue", "NWC % revenue",
        ],
        "Value": [
            f"{a['wacc']:.2%}", f"{a['terminal_growth']:.2%}", f"{a['revenue_growth_start']:.2%}",
            f"{a['ebitda_margin']:.2%}", f"{a['tax_rate']:.2%}", f"{a['da_pct_revenue']:.2%}",
            f"{a['capex_pct_revenue']:.2%}", f"{a['nwc_pct_revenue']:.2%}",
        ],
    }))

st.divider()
st.caption(
    "Data: Yahoo Finance via yfinance (not Bloomberg-grade). No buy/sell/hold "
    "recommendation — the output is an input to analyst judgement, not a substitute for it."
)
