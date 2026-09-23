# Ideas parking lot

Out-of-scope ideas and notes go here. Nothing in this file gets built during
the 5-day sprint unless explicitly moved into CLAUDE.md scope.

## Notes

- **2026-09-22**: Sika AG (`SIKA.SW`) currently trades at ~CHF 29.7bn market
  cap, which is above the €1-10bn mid-cap definition in §2. This is a settled
  decision (§3) and not being reopened — noting it here so it can be mentioned
  honestly in the README limitations section (Day 5) as "demo company is
  larger than the tool's stated universe, chosen for recruiter recognition."

- **2026-09-23 (post-sprint idea)**: Use AI to help pick which valuation
  metrics fit a given company (e.g. flag when EV/Sales is misleading because
  the target's margin differs sharply from peers). Not built in the sprint.
  → Folded into roadmap item 2 below.

## Post-sprint roadmap (requested 2026-09-23, not started)

1. **Peer group selection criteria.** Today: hand-tagged `peer_group` +
   EUR 1-10bn band + market-cap proximity. Ideas: explicit criteria
   (end-market, margin profile, growth, geographic mix), show *why* each peer
   was picked, let the user add/remove peers in the UI, and allow peers
   outside the EU mid-cap band (Sika has no true peer inside it).
2. **Which multiples to use.** Include all mainstream multiples (EV/EBITDA,
   EV/EBIT, EV/Sales, P/E, P/B, FCF yield, ...), then rank each one's
   reliability for the specific target, e.g. EV/Sales flagged unreliable for
   Sika because its margin is far above peers; P/E unreliable when peers
   have negative or depressed earnings. Could be rule-based first, AI-assisted
   later (the earlier idea above).
3. **Analyst consensus target price.** yfinance `info` already exposes
   targetLow/Mean/Median/HighPrice and numberOfAnalystOpinions (checked
   2026-09-23: Sika 21 analysts, low 150 / mean 200 / high 233 CHF; Nolato
   only 2). Natural fit: a 4th football-field bar. Show analyst count and
   hide/grey out when coverage is thin. Keep the "no buy/sell recommendation"
   boundary: show the third-party target range, not the rating
   (`recommendationKey`).
4. **Where key inputs come from.** Replace hand-set sector WACC with a
   sourced build-up: risk-free (e.g. Swiss Confederation / Bund 10Y yield),
   beta (yfinance `beta`, Sika 1.199), equity risk premium (e.g. Damodaran),
   cost of debt (interest expense / debt from statements), weights from
   market cap and net debt. Growth: consensus revenue estimates instead of
   historical CAGR (check what yfinance exposes). Show each input's source.
5. **Interactive sensitivity analysis.** Sliders/inputs for WACC, terminal
   growth, revenue growth, EBITDA margin, CapEx %, NWC %; a 2-D grid where
   the user picks which two inputs are on the axes. Low effort: dcf.py's
   `forecast_free_cash_flows(assumptions, wacc, g)` already takes an
   assumptions dict, so overrides slot straight in.

Before starting: write a scope + time budget for this phase (as CLAUDE.md
did for the sprint). Suggested order by effort vs value: 5 → 3 → 4 → 1 → 2.

## Session log
- **2026-09-23 (Day 4 end)**: App live at https://eu-midcap-research-tool.streamlit.app
  (public app, repo still private — flip repo public on Day 5). Verified from a
  logged-out browser: SIKA.SW and WEIR.L (cold, GBp) render in ~30s. Streamlit
  Cloud must run Python 3.12 — pinned pandas/numpy/pyarrow have no 3.14 wheels.
  Open decision for user: EV/Sales systematically undervalues Sika (18% EBITDA
  margin vs lower-margin peers) — replace with P/E or drop. Next: Day 5 narrative.
- **2026-09-23 (Day 5)**: README, ATTRIBUTION.md, case_studies/sika_initiation.md
  and 3 screenshots (captured from the live app) done. Remaining: user to
  review the "Why I built it" / Development wording, then flip repo public.
- **2026-09-23 (sprint end)**: Commit emails rewritten to tung-hsien.lee@proton.me;
  repo made public. All Day 1-5 done-criteria met. Open for user review: README
  "Why I built it" wording, ATTRIBUTION "Development" wording, MBCC claim in the
  case study, and the Day 2 manual check of 3 numbers (add to README Testing).
- **2026-09-23 (post-sprint fixes)**: Manual check vs Sika AR 2025 — revenue
  exact, net profit differs only by CHF 1.3m minorities (tool uses attributable,
  correct for P/E), net debt was 10% low because Yahoo's "Net Debt" excludes
  IFRS 16 leases. Fixed: net debt = total debt (incl. leases) - cash → 4,716m vs
  4,734.5m reported; ND/EBITDA 2.26x vs 2.3x. Sika DCF 128.8 → 126.1 CHF; case
  study, README (verification table) and screenshots updated. Found and fixed a
  stale-cache bug on Streamlit Cloud: CACHE_VERSION now in the parquet filename
  and st.cache_data key — bump it whenever a stored field's definition changes.
  Live app verified at 126.10. Next: scope the post-sprint roadmap above.
