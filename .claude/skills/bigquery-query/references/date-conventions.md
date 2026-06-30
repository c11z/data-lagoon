# Date / timezone conventions

Subtly-wrong dates are a large class of wrong analytics answers. Apply these consistently.

- **"Last week" / "last month"** = the last **complete** calendar week/month — **not**
  trailing 7 / 30 days. Be explicit in the answer about the exact window used.
- **As-of vs trailing-N**: state which you used. Trailing windows on google_trends should
  filter `refresh_date` (the partition), e.g. `refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)`.
- **Freshness**: anchor on `MAX(refresh_date)`, never "yesterday". Some refreshes land late;
  report the actual `MAX(refresh_date)`.
- **`week` vs `refresh_date`**: `week` is the Sunday the ranking is *about*; `refresh_date`
  is when Google *published* it (and the partition column). Filter `refresh_date` for cost;
  group/report by `week` for analysis.
- **Timezone**: default UTC. google_trends columns are DATEs (no time component).

## "What was trending last complete week" — correct shape

```sql
-- last complete week = the most recent Sunday-started week that has fully elapsed
WHERE week = DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 WEEK), WEEK(SUNDAY))
    AND refresh_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 21 DAY)  -- partition prune
```
