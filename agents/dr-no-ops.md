# Agent: Dr. No (Ops Monitor)

> Infrastructure health monitoring. Checks all production systems and reports status. **Never takes remediation action — report only.**

## Trigger

- Daily at 6:00 AM (routine sweep)
- Weekly Monday (always post summary, even if all green)
- On-demand (when other agents detect errors)

## Design Philosophy

Dr. No uses **zero LLM credits**. Every check is a bash command:
- `curl` for HTTP health checks
- `ssh` + `systemctl` for service status
- `psql SELECT 1` for database connectivity
- File timestamp checks for cron health

This is intentional. The ops monitor must not depend on the same infrastructure it monitors. If the LLM API is down, Dr. No still runs.

## Health Checks

### HTTP Endpoints
```bash
curl -s -o /dev/null -w "%{http_code} %{time_total}" --max-time 10 https://your-site.com
```

| Metric | GREEN | YELLOW | RED |
|--------|-------|--------|-----|
| HTTP status | 200 | — | non-200 |
| Response time | < 2s | 2-5s | > 5s or timeout |

### Service Health (via SSH)
- `systemctl is-active <service>` — must return `active`
- Disk: GREEN < 80%, YELLOW 80-90%, RED > 90%
- Memory: GREEN > 200MB free, YELLOW 100-200MB, RED < 100MB

### Database Connectivity
- `SELECT 1` via connection pooler
- Timeout: 5s. Failure = RED.
- Read-only. Never write.

### Cron Health
- Check last-modified timestamp of each cron's state file
- YELLOW if last run > 1.5x expected interval
- RED if last run > 2x expected interval

## Output Format

### Daily (only post if YELLOW or RED exists)
```
[OPS] Health Check — 2026-05-08 06:00 PT

YELLOW  site-a.com — Response time 2.8s (threshold 2s)
RED     site-b.com — HTTP 503 Service Unavailable

Degraded: 1 | Down: 1 | Healthy: 8

Action needed:
- site-b.com returning 503. Check deployment status.
```

### Monday Summary (always post)
```
[OPS] Weekly Systems Report — Week of 2026-05-05

All Systems: 10/10 GREEN

7-day uptime:
  site-a.com          99.8% (1 YELLOW event Thu)
  site-b.com          100%
  gateway service     99.4% (2 RED events Tue)

Incidents this week: 3
Trend: Stable.
```

### Critical Alert (immediate)
```
[OPS] ALERT — RED

site-b.com is DOWN
HTTP 503 at 2026-05-08 14:32 PT
Last healthy: 2026-05-08 13:00 PT
```

## Alerting Rules

- GREEN on non-Monday: suppress from Slack
- YELLOW: include in daily report
- RED: post immediately, don't wait for daily sweep
- RED re-check: automatically verify 15 minutes later. If recovered, downgrade to YELLOW with note.

## Deduplication

Don't re-alert the same RED condition within 4 hours. Exception: if a system goes RED → GREEN → RED, that's a new incident.

## State Tracking

Append-only JSONL:
```json
{"ts": "2026-05-08T13:00:00Z", "system": "site-a.com", "status": "GREEN", "http_code": 200, "response_ms": 142}
```

Retain 30 days, rotate on each run.

## Approval Gate

None. Dr. No is read-only. No approval needed to check health and post status.

**HARD RULE: If Dr. No detects an issue, the ONLY action is to report it. Never SSH in and restart. Never redeploy. Never modify configs. The operator handles all remediation.**
