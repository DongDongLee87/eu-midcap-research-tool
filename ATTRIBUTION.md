# Attribution

## virattt/dexter — conceptual influence, no code

[Dexter](https://github.com/virattt/dexter) (MIT licence, TypeScript/Bun) is an autonomous financial-research agent. It breaks a question into a research plan, picks tools such as `get_income_statements` to gather market data, checks its own work, and logs every tool call to a JSONL scratchpad.

**What this project took from it:** the idea of splitting financial research into small, single-purpose data tools — one module for financials, one for comparables, one for valuation. That is why the modules live under `src/tools/`.

**What it deliberately did not take:** the agent loop itself. The original design used Dexter's plan–act–reflect loop and scratchpad. I removed it once the workflow was clear. A valuation initiation follows a fixed sequence (statements → peers → multiples → DCF → football field), so no step needs a model to decide what comes next. An agent layer would add latency and the risk of hallucinated figures, and give no analytical benefit in return. The pipeline here is deterministic: the same inputs always produce the same outputs, and each number can be traced back to a line of code.

No Dexter source code is used in this repository. The two projects are written in different languages and share no files.

## Data

- **Yahoo Finance** via [`yfinance`](https://github.com/ranaroussi/yfinance) (Apache 2.0). Yahoo data is intended for personal use. This project is a non-commercial demonstration and redistributes no data beyond what the app displays.

## Libraries

- [Streamlit](https://streamlit.io) — UI and hosting (Streamlit Community Cloud)
- [Plotly](https://plotly.com/python/) — football-field chart
- [pandas](https://pandas.pydata.org), [NumPy](https://numpy.org), [PyArrow](https://arrow.apache.org) — data handling and parquet cache

## Development

The code was written with an AI pair-programmer (Claude Code), and the commits are co-authored accordingly. I made the scope, peer-universe curation, valuation methodology and validation decisions, and reviewed every output manually.
