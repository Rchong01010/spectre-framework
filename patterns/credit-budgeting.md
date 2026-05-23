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
| Web scraping API | Per-run credit budgets | Web search + scrape |
| LLM API | Per-call pricing | Content analysis, drafting |

### 4. Track credit usage in output

Every agent's output includes credits consumed:

```
Credits used: 12/20 this run
```

This makes budget management visible without checking billing dashboards.

## Monthly Cost Model (Pattern)

To estimate your fleet cost, calculate per-agent:

| Variable | Formula |
|----------|---------|
| Runs/month | Schedule frequency x 30 |
| Credits/run | Set in skill spec |
| Max monthly credits | Runs x credits/run |
| API cost | Credits x provider rate |

**Key insight:** Agents that don't require LLM inference (health checks, security scans) cost $0 in API fees. Design as many agents as possible to use free tooling (`curl`, `ssh`, `semgrep`, etc.), and reserve LLM calls for tasks that genuinely require language understanding. The entire fleet can run on a minimal VPS plus free-tier services.

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
