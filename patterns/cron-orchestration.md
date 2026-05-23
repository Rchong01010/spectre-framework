# Pattern: Cron Orchestration — LLM vs Deterministic

## The Lesson Learned the Hard Way

Early design: every task ran on the LLM executor (OpenAI Codex / Claude API). Health checks, email sends, enrichment queries — all routed through the same API.

What happened: a rate limit on the LLM API cascaded into:
1. Health checks stopped firing (looked like system-wide outage)
2. Email sends backed up (missed approval windows)
3. Reply monitoring went silent (missed interested prospects)
4. The "death spiral" — the monitoring agent couldn't detect the problem because it was affected by the same problem

## The Fix: Two Execution Layers

### Layer 1: Deterministic tasks (local crontab)
Tasks that can be expressed as bash/Python scripts without LLM inference:
- HTTP health checks (`curl`)
- Service status checks (`systemctl`, `ssh`)
- Database connectivity (`psql SELECT 1`)
- Email sending (Gmail API, already-drafted content)
- SMTP verification
- Log rotation
- Cron timestamp logging

### Layer 2: LLM tasks (remote executor)
Tasks that require language understanding:
- Content scanning and reply drafting
- Prospect qualification
- Email personalization
- Reply classification (interested vs. bounce vs. OOO)
- Content generation

**Rule: If the task can be a bash script, it must be a bash script.**

## Cron Design Principles

### 1. Order by dependency

```
6:45 AM — Enrich prospects (find emails)
7:00 AM — Verify emails (SMTP check)
7:30 AM — Draft outreach (LLM personalization)
7:35 AM — Send approval batch to operator
8:30 AM — Send approved emails
```

Each step depends on the previous. If enrichment fails, verification runs on an empty set (no harm). If drafting fails, no approval batch is sent (no harm). No step corrupts data if a predecessor fails.

### 2. Idempotency

Every cron job must be safe to re-run:
- `email_verifier.py --batch 200` — skips already-verified emails
- `reply_monitor.py --since-hours 4` — only looks at the recent window
- `campaign_runner.py` — enrollment is idempotent (INSERT ON CONFLICT DO NOTHING)

If cron fires twice in a row, nothing breaks.

### 3. Graceful degradation over hard failure

```python
# Bad: crash if API is down
response = requests.get(url)  # raises on timeout
data = response.json()

# Good: degrade and log
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    log(f"Enrichment API unavailable: {e}. Skipping batch.")
    return  # Next cron cycle will retry
```

### 4. Cron state tracking

Every cron job logs its runs to a shared table:
```sql
INSERT INTO cron_log (job_name, started_at, completed_at, status, records_processed, error_message)
VALUES ('email_verifier', now(), now(), 'success', 200, NULL);
```

The ops monitor (Dr. No) reads this table to detect stale crons. If `email_verifier` hasn't logged a run in 25 hours on a weekday, it's flagged YELLOW.

### 5. Kill switches are permanent

When a pipeline is killed (e.g., cold outreach channel proved dead):
1. Comment out the cron line
2. Add a note in the cron file explaining WHY it was killed
3. Leave the script on disk (don't delete)
4. Document in the repo's instruction file

**Never silently re-enable a killed pipeline.** The kill happened for a reason.

## Budget Considerations

| Layer | Monthly cost | Failure mode |
|-------|-------------|--------------|
| Local crontab | $0 | Machine sleep/reboot (expected, recoverable) |
| LLM executor | Variable (budget-capped) | Rate limits, API outages (design for graceful degradation) |

Keep LLM costs predictable by setting credit budgets per agent per run. If an agent is allocated 20 credits per run and runs 8x/month, the maximum monthly cost for that agent is 160 credits — known in advance.
