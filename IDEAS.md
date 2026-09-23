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
