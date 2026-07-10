# Financial Monitor Agent Guide

## Project Rules

- Treat `generate_dashboard.py` as the official dashboard generator and `dashboard.html` as generated output.
- Do not edit `dashboard.html` directly unless the user explicitly asks for a prototype or generated HTML patch.
- Keep unrelated user changes intact. Check `git status --short` before and after edits.
- Prefer narrow, verifiable changes. Run the smallest useful validation for the files touched.

## Shared Skills

- `.agents/skills/` is the canonical source for project skills.
- `.codex/skills/` and `.claude/skills/` are generated copies for each tool.
- Edit skills only in `.agents/skills/`.
- After changing a skill, run `powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1`.
- Use `powershell -ExecutionPolicy Bypass -File scripts/sync-skills.ps1 -DryRun` to inspect the sync without writing.
- Validate changed skills with `python C:\Users\phill\.codex\skills\.system\skill-creator\scripts\quick_validate.py <skill-folder>` when available.

## Dashboard Work

- After Python changes, run `python -m py_compile generate_dashboard.py`.
- After generator changes, run `python generate_dashboard.py` when data access is available.
- The generator may update `dashboard.html` and snapshot history as part of normal operation.

## Production Execution

- Production cadence is owned by an external cron service that triggers the GitHub Actions `workflow_dispatch` event.
- The GitHub Actions `schedule` block is intentionally disabled. Do not recommend enabling it unless the user explicitly wants to change scheduling ownership; enabling both would create duplicate runs.
- Pushes to `main` or `master` also run the workflow and deploy the generated dashboard to GitHub Pages.

## Data Sources and Fallbacks

- Weekly/monthly RSI, current price, volume, and the table's `DD 5A` use Yahoo Finance data.
- Historical crypto drawdown uses CoinMetrics as the primary source. Yahoo Finance is an accepted fallback when CoinMetrics does not expose the required asset/metric to the current endpoint or credentials.
- A disclosed fallback is traceability information, not automatically a data error or publication blocker.
- Historical drawdown for non-crypto assets uses Yahoo Finance auto-adjusted close data.

## Historical Data Quality

- Older Brazilian equity histories can contain artificial adjustment discontinuities that would distort worst drawdown, CAGR, and drawdown percentiles.
- The generator intentionally trims the series at the latest detected adjustment break when enough usable history remains.
- Do not remove this cleanup merely to maximize the displayed history length. Validate its effect on historical risk metrics before changing its thresholds or behavior.

## Coverage and History Persistence

- `finance_stocks.py::assets` is the canonical asset universe. Derive expected coverage from it; do not hardcode totals such as 121 or 122.
- The Data Contract must compare configured versus rendered assets and expose real omissions instead of silently reducing coverage.
- Local runs do not persist snapshot history unless `FM_PERSIST_HISTORY=1` is set.
- Production sets `FM_PERSIST_HISTORY=1`; the workflow commits `snapshot_history.json` and `signal_history.json` so signal changes and KPI deltas survive between runs.

## Financial Semantics and Intended Behavior

- Weekly and monthly RSI signals intentionally use the latest available market data, including the current in-progress period.
- Signals are intended to reflect the current market condition and may change before the weekly or monthly period closes. This is expected behavior, not a reliability defect.
- Do not classify current-period RSI as "unconfirmed" or "provisional", and do not expose an `OPEN_WEEKLY_BAR` data-quality warning.
- Do not recommend waiting for a closed weekly bar unless the user explicitly requests a strategy change.
- Volume confirmation intentionally uses the last closed weekly bar and compares it with the previous four completed weeks.
- The table's `DD 5A` intentionally measures drawdown from the most recent peak inside the five-year window.
- The drawdown modal intentionally shows both five-year current drawdown and historical current drawdown. These values are not expected to match.
- Historical drawdown requests up to 30 years but displays the actual available history when an asset has less data.
- Do not recommend unifying five-year and historical drawdown horizons unless the user explicitly requests it.
