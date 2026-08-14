# Executive Summary — Design Spec

**Date:** 2026-07-28
**Issue:** #22 (Rep Stats) — additional view
**Branch:** `feat/rep-stats`

## Summary

A live Executive Summary dashboard under the Metrics nav group. Aggregates data from `deal_ui` (already loaded) and `deals` (for partner/size fields). No dependency on weekly pipeline or `learned_patterns`.

Primary audience: Leadership reviewing overall sales performance.

## Navigation

Added to existing Metrics group in `nav-items.ts`:

```
Metrics (icon: calculator)
  ├── Exec Summary (key: "execsummary", icon: presentation, slug: "exec-summary")
  └── Rep Stats (key: "repstats", icon: trendUp, slug: "rep-stats")
```

## Data Layer

### Hook: `ui/src/data/useExecSummary.ts`

**Primary source**: `useData()` from store — already loaded, zero extra queries.
- `forecast.allDeals` — all open deals
- `forecast.closedDeals` — won deals this month
- `forecast.lostDeals` — lost deals this month
- `benchmark.won` / `benchmark.lost` — historical closed deals with close dates

**Secondary source**: One Supabase query to `deals` for `partner` and `num_employees` (not in deal_ui).

**Date filtering**: MTD by default. User can select month via a month picker. Filters `benchmark.won`/`benchmark.lost` by `closeDate` and open deals by current state.

## Layout — Single Scrollable Page

### Section 1: Top KPI Cards (6 cards)
| KPI | Source | Format |
|---|---|---|
| MRR Won | sum of closed-won deals' MRR in period | EUR |
| Demos Held | count of deals with demo stage in period | integer |
| Logos Won | count of closed-won deals in period | integer |
| Open Pipeline | sum of open deals' MRR | EUR |
| Win Rate | won / (won + lost) in period | percentage |
| Avg Sales Cycle | avg deal_age of won deals in period | days |

### Section 2: Team Performance Table
Rows: one per active team. Columns: Team, MRR Won, Demos, Logos, Pipeline, Win Rate, Avg Cycle. Sortable.

### Section 3: Pipeline Analysis
- Stage distribution: deal count + MRR per macro_stage (from open deals)
- Forecast categories: Commit / Pipeline / Upside / Omit counts + MRR

### Section 4: Loss Analysis
- Top loss reasons: closed_lost_reason frequency, top 5

### Section 5: Partner Performance (from deals query)
- Table: Partner, MRR Won, Deals, Pipeline per partner. Sortable.

## File Structure

### New files
```
ui/src/
  data/useExecSummary.ts
  views/metrics/ExecSummaryView.tsx
```

### Edited files
```
ui/src/
  layout/nav-items.ts
  App.tsx
  permissions.tsx
```
