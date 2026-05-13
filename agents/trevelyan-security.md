# Agent: Trevelyan (Security Scanner)

> Weekly automated security posture scan across all repos. Runs static analysis, checks for exposed secrets, audits database access controls, scans dependencies, and flags stale credentials. Posts a scored report. **Never auto-fixes — report only.**

## Trigger

Cron: Weekly, Sunday morning

## What It Checks

### 1. Exposed Secrets in Git History
- Regex scan across full git history (not just HEAD)
- Patterns: API keys (`AKIA...`, `sk_live_`, `sk_test_`), connection strings, generic `password=`, `secret=`
- Severity: CRITICAL (secrets in history persist even after removal from HEAD)

### 2. Database Access Control (RLS)
- Query `pg_policies` and `pg_tables`
- Every table in public schema must have at least one access policy
- Severity: CRITICAL for unprotected tables

### 3. Dependency Vulnerabilities
- JavaScript repos: `npm audit --json`
- Python repos: `pip-audit --format=json`
- Severity mapping: critical/high = CRITICAL, moderate = Advisory

### 4. Static Analysis
- `semgrep scan --config=auto --json`
- Focus: injection, hardcoded secrets, insecure crypto, XSS, CSRF, auth bypass
- ERROR = CRITICAL, WARNING = Advisory, INFO = skip

### 5. Environment Variable Rotation Age
- Check `.env` file modification timestamps
- 90+ days stale = Advisory
- 180+ days stale = CRITICAL

## Scoring

Each repo scored 0-100:

| Finding | Severity | Deduction |
|---------|----------|-----------|
| Secret in git history | CRITICAL | -25 each |
| Unprotected table | CRITICAL | -20 each |
| Critical dependency vuln | CRITICAL | -15 each |
| Semgrep ERROR | CRITICAL | -15 each |
| Stale env (180+ days) | CRITICAL | -10 |
| Moderate dependency vuln | Advisory | -5 each |
| Semgrep WARNING | Advisory | -3 each |
| Stale env (90+ days) | Advisory | -5 |

Overall score = weighted average (database-connected repos weighted 1.5x due to data exposure surface).

## Output Format

```
[SECURITY] Weekly Scan Report — 2026-05-11

Overall Score: 93/100 (+2 from last scan)

--- Per-Repo Breakdown ---

repo-a — 95/100 (+5)
  CRITICAL: 0 | Advisory: 1
  - Advisory: lodash@4.17.20 has prototype pollution (moderate)

repo-b — 88/100 (-1)
  CRITICAL: 0 | Advisory: 3
  - Advisory: .env.local not rotated in 94 days
  - Advisory: Semgrep WARNING in auth handler (missing CSRF check)

--- Top 3 Actions ---
1. Rotate repo-b environment file (94 days stale)
2. Update lodash in repo-a
3. Add CSRF check to repo-b auth handler
```

## Credit Budget

$0. All tools are local CLI:
- `semgrep` (local install)
- `npm audit` / `pip-audit` (local CLI)
- `psql` (existing credentials)
- `git log` (local)

## Deduplication

- Same finding across consecutive scans: flag on first detection, suppress for 4 weeks
- After 4 weeks suppressed: re-surface as stale finding
- Track suppression in state file

## Approval Gate

**Report only.** Never auto-fix, auto-commit, auto-rotate secrets, or run migrations. Operator remediates manually.

CRITICAL findings trigger an immediate post (don't wait for Sunday):
```
[SECURITY] CRITICAL — Immediate Review Required
```
