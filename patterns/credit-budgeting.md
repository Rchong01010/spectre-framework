# Pattern: Credit Budgeting for Agent Fleets

## The Problem

LLM APIs and web scraping services charge per-call. An agent fleet running 6x/day across 8 agents can burn through free tiers or run up bills fast — especially during edge cases (retry loops, broad searches, unexpected content volumes).

## The Solution: Per-Agent, Per-Run Budgets

Every agent's skill spec declares its credit budget:

```markdown
## Credit Budget

- Per-run limit: 20 Firecrawl credits
- Queries per run: 4-6 search queries (3-4 credits each)
- If credits are low, reduce to 3 queries (don't fail)
- Monthly budget: ~160 credits (8 runs x 20 credits)
```

## Budget Design Principles

### 1. Budget per run, not per month

Monthly budgets create unpredictable spending patterns. An agent might use 80% of its monthly budget in the first week, then starve. Per-run budgets create consistent, predictable costs.

### 2. Graceful degradation, not failure

```python
# Bad: crash when budget exhausted
if credits_remaining < credits_needed:
    raise BudgetExhaustedError()

# Good: reduce scope and continue
if credits_remaining < full_budget:
    queries = queries[:3]  # Reduce from 6 to 3 queries
    log("Credits low — running reduced query set")
```

An agent that finds 2 prospects with 3 queries is better than an agent that finds 0 because it crashed.

### 3. Zero-cost agents exist

Not every agent needs API credits. Design agents to use free tools first:

| Tool | Cost | Use for |
|------|------|---------|
| `curl` | Free | HTTP health checks |
| `ssh` + `systemctl` | Free | Service status |
| `psql` | Free | Database queries |
| `semgrep` | Free | Static analysis |
| `npm audit` | Free | Dependency scanning |
| `git log` | Free | History scanning |
| Firecrawl (free tier) | ~150 credits/day | Web search + scrape |
| LLM API | ~$0.01-0.10/call | Content analysis, drafting |

### 4. Track credit usage in output

Every agent's output includes credits consumed:

```
Credits used: 12/20 this run
```

This makes budget management visible without checking billing dashboards.

## Monthly Cost Model (Real Numbers)

| Agent | Runs/Month | Credits/Run | API Cost | Total |
|-------|------------|-------------|----------|-------|
| Oddjob (Scanner) | 180 (6x/day) | 8 Firecrawl | ~$0 (free tier) | $0 |
| Dr. No (Ops) | 30 (daily) | 0 | $0 | $0 |
| Elektra (Inbound) | 90 (3x/day) | 5 Firecrawl | ~$0 | $0 |
| Goldfinger (Prospector) | 8 (2x/week) | 20 Firecrawl | ~$0 | $0 |
| Trevelyan (Security) | 4 (weekly) | 0 | $0 | $0 |
| Janus (Scout) | 4 (weekly) | 10 Firecrawl | ~$0 | $0 |
| Scaramanga (Content) | ~10 (on-demand) | 0 | ~$2 LLM | $2 |
| Moneypenny (Analyst) | ~5 (on-demand) | 0 | ~$3 LLM | $3 |
| **LLM executor overhead** | — | — | ~$15 | $15 |
| **Total** | | | | **~$20/mo** |

The entire 8-agent fleet runs for about $20/month in API costs. Infrastructure (Hetzner VPS) adds ~$7/month. Total: **~$27/month** for a fully autonomous agent fleet.

## Overspend Prevention

### Hard caps
Some APIs support spending limits. Enable them:
- OpenAI: Monthly spending cap in settings
- Anthropic: Usage limits per API key

### Soft caps in code
```python
MAX_CREDITS_PER_RUN = 20

credits_used = 0
for query in queries:
    if credits_used >= MAX_CREDITS_PER_RUN:
        log(f"Budget exhausted ({credits_used}/{MAX_CREDITS_PER_RUN}). Stopping.")
        break
    result = search(query)
    credits_used += estimate_credits(result)
```

### Alert on anomalies
If an agent uses >150% of its normal budget in a single run, post an alert:
```
[BUDGET] Oddjob used 14/8 credits this run (175% of budget)
Cause: 3 retries on rate-limited search endpoint
```
