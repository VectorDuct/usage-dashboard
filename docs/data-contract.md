# Aggregate source contract (v1)

File and HTTP sources return this shape. No provider is auto-detected: write a small exporter to translate your provider's response. The server never invokes a model, edits accounts, or reads provider databases.

```json
{
  "generated_at": "2026-01-01T12:00:00Z",
  "window": {"date": "2026-01-01", "timezone": "UTC"},
  "models": [
    {"id": "chat-a", "label": "Chat A", "unit": "requests", "used": 120,
     "limit": 1000, "requests": 125, "successes": 120, "failures": 5,
     "estimated": true}
  ]
}
```

Replace the illustrative timestamp/date with **the actual upstream observation time and current source date**. Never stamp a stale cached result as fresh. An expired example intentionally displays unavailable.

- `generated_at`: ISO 8601 with timezone. Accepted age is at most `stale_after` seconds; at most 5 seconds of future clock skew. Observation and current time must both fall in `window.date` in `window.timezone`.
- `window`: daily calendar window in an IANA timezone. The frontend's display timezone does not change source accounting. Monthly/rolling windows are not supported in v0.1.
- `models`: at most 200 rows. `(id, unit)` must be unique per source. IDs/labels are public text, max 160 characters; never use account identifiers here.
- `unit`: `requests` or `tokens`. These units never merge.
- `used`, `limit`: non-negative integer or `null` (missing also means unknown). Never use 0 to represent an unknown quota. `used` may exceed `limit`.
- Optional `remaining`: source-reported balance after per-account capping, non-negative and at most `limit`. Requires known `used` and `limit`. If absent, `max(0, limit-used)` is used. Explicit `null` remains unknown. Report this field if summing independently capped accounts; raw observed usage may differ from quota consumption.
- `requests`, `successes`, `failures`: optional integer counters for this same daily window, not lifetime totals. Success rate is shown only when all outcomes are known and sum to `requests`; missing/in-flight outcomes remain unknown. Do not count the same request twice within a row. A source can expose multiple units for one model; request counts on those rows overlap and are not summed across units.
- `estimated`: boolean, default false. Use true for estimated rather than contractual quota values.
- Integers are bounded to JavaScript's safe integer range. Negative, boolean, fractional, duplicate or malformed values reject the entire source sample.
- All fields outside the allowlist are discarded before serving or storing. The dashboard does not sanitize secrets accidentally placed **inside** allowed label/id fields; exporters must publish aggregate, non-sensitive labels.

## Aggregation

Only identical model ID, unit, date and timezone combine. **Sources must represent disjoint usage/quota pools.** Two endpoints describing the same pool would double-count. Do not configure private/internal sources on a public dashboard. Disabling a source removes its live view and history from the API (stored history remains local).

Balances sum per source, after capping, rather than subtracting combined attempts from combined quotas. Any enabled unavailable/stale source marks aggregate rows partial and hides total limits/balances. Request/usage numbers then describe fresh sources only. A configured source's empty model list means it explicitly reports no models; missing sources are different. Unknown fields propagate through sums; unknown is never silently treated as zero.

## API

- `GET /api/dashboard`: site title/description/language, display timezone, source freshness, whitelisted current models and combined rows. `generated_at` is API response time; each source carries its actual observation time in `data.generated_at`.
- `GET /api/history`: `{ "snapshots": [{ "source_id": "team", "data": { ...normalized sample... } }] }`. Latest observation per source/date/timezone, newest dates first; max 128 snapshots per response. The UI shows up to 40 model rows. Removed/disabled sources are filtered.
- `GET /healthz`: process liveness. It does not prove healthy sources.
- `GET /readyz`: 200 only when all enabled sources are fresh; otherwise 503.
- `/`, `/app.js`, `/style.css`: fixed asset routes. No directory/file server, write API or browser-side credentials.

## History semantics

SQLite stores **absolute snapshots**, not request events. Repeated polling replaces the same day's sample rather than adding counts; older observations cannot overwrite newer ones. Retention is `history_days` × 24 hours by observation timestamp; pruning happens after successful writes. Read filtering applies even without new writes. It cannot recover pre-installation history or guarantee end-of-day totals during downtime; a source counter reset may replace that day's prior snapshot. Runtime data is ignored by Git and excluded from release bundles.

## Naoya adapter

`type: "naoya"` logs in with the configured environment variable references, then reads `/api/dashboard/realtime`. Login is only for a console session; no Google/account login or generation occurs. Cookies stay in process memory for that fetch. A successful login’s 302/303 response to `/` is accepted without following it; all other redirects are refused. No upstream body/error is published.

The adapter targets the realtime-summary dialect with `generated_at`, `status.browser_connected/service_connected`, and `scheduler.usage_window/models/quota_by_model/token_quota_by_model`. Both runtime status flags must be true. Request quota occupancy uses `total_quota - estimated_remaining_quota`; requests use the model's `daily_requests`. It does not infer outcomes.

Token quotas require `token_metric: total_tokens`, matching windows and scope `build/model` or `build/account`. Account-shared pools appear once as `pool:<pool>`; repeated identical pool projections deduplicate, conflicting projections reject the sample. Unknown usage/limits remain unknown; supplied estimated balances are preserved. Other scopes/metrics are omitted. This is **not a promise of compatibility with every Naoya version**; verify an aggregate-only fixture from your version. Remote HTTP is refused: use HTTPS or a loopback tunnel.
