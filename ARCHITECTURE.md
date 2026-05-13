# System Architecture

## Overview

This document describes the full architecture of a production AI agent system that operates a multi-brand business. The system has three layers:

1. **Agent Fleet** — LLM-powered agents that scan, analyze, draft, and report
2. **Automation Layer** — Deterministic Python scripts for pipeline operations
3. **Infrastructure** — VPS, databases, web properties, notification hub

## Layer 1: Agent Fleet (SPECTRE)

Eight agents, each defined by a declarative skill specification. No shared state between agents except through the database and Slack channel.

### Agent Roster

| Agent | Role | Schedule | LLM Required | Credit Budget |
|-------|------|----------|-------------|---------------|
| Oddjob | Multi-platform content scanner | 6x/day (every 4h) | Yes (content analysis) | 8 Firecrawl/run |
| Dr. No | Infrastructure ops monitor | Daily 6am + on-demand | No (curl + ssh + psql) | $0 |
| Elektra | Inbound signal detector | 3x/day | Yes (reply classification) | 5 Firecrawl/run |
| Goldfinger | Prospect sourcer | 2x/week | Yes (qualification) | 20 Firecrawl/run |
| Trevelyan | Security posture scanner | Weekly Sunday | No (Semgrep + npm audit) | $0 |
| Janus | Market intelligence scout | Weekly Monday | Yes (analysis) | 10 Firecrawl/run |
| Scaramanga | Content drafter | On-demand | Yes (voice matching) | $0 |
| Moneypenny | Financial/thesis analyst | On-demand | Yes (analysis) | $0 |

### Key insight: Not every agent needs an LLM

Dr. No and Trevelyan run entirely on `curl`, `ssh`, `psql`, `semgrep`, and `npm audit`. Zero API cost. Early versions routed everything through the LLM executor, which caused:
- API rate limit cascading (one agent's burst starved others)
- $20+/day in unnecessary API calls
- False reliability failures (LLM timeout ≠ system down)

**Rule: If the task can be done with a bash script, it should be a bash script.**

### Agent Communication Model

```
Agent → Slack Channel → Human → Action

Agents do NOT communicate with each other directly.
All inter-agent coordination happens through:
  1. Shared database tables (read-only for most agents)
  2. The Slack channel (human reads one agent's output, invokes another)
  3. State files on the filesystem (JSONL append-only logs)
```

This eliminates an entire class of bugs: agent A tells agent B to do something that agent B shouldn't do. The human is always in the loop.

## Layer 2: Automation Layer (GTM Pipeline)

60+ Python scripts handling deterministic business operations. These run on local crontab, not on the LLM executor.

### Email Pipeline Architecture

```
                                        ┌──────────────┐
                                        │  State Bar   │
                                        │  Registry    │
                                        └──────┬───────┘
                                               │
                                               ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Registry    │───▶│  Enrichment  │───▶│   SMTP       │
│  Scraper     │    │  Pipeline    │    │  Verifier    │
│              │    │  (Claude +   │    │              │
│  Import raw  │    │   IPQS +     │    │  MX lookup + │
│  prospects   │    │   Court +    │    │  RCPT TO     │
│              │    │   OpenCorp)  │    │              │
└──────────────┘    └──────────────┘    └──────┬───────┘
                                               │
                                               ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Reply       │◀───│  Gmail       │◀───│  Email       │
│  Monitor     │    │  Sender      │    │  Drafter     │
│              │    │              │    │              │
│  Classify:   │    │  Max 5/day   │    │  A/B: value  │
│  interested  │    │  Pre-send    │    │  vs loss     │
│  / bounce /  │    │  EVA+Kickbox │    │  aversion    │
│  OOO / etc   │    │  filter      │    │              │
└──────┬───────┘    └──────────────┘    └──────────────┘
       │                    ▲
       │                    │
       ▼              ┌─────┴──────┐
┌──────────────┐      │  Approval  │
│  Auto-Reply  │      │  Gate      │
│  (interested │      │            │
│   prospects) │      │  HMAC URLs │
│              │      │  → Vercel  │
└──────────────┘      │  endpoint  │
                      └────────────┘
```

### Approval Gate Pattern

Every email goes through an explicit approval flow:

1. **Drafter** generates personalized email (Claude) → status: `pending_approval`
2. **Approval batch** sends operator an email with HMAC-signed Approve/Skip links
3. Operator clicks Approve → hits Vercel serverless function → verifies HMAC → updates DB status to `approved`
4. **Sender** picks up `approved` emails on next cron cycle → sends via Gmail API
5. Operator can also click Skip → email never sends

No email is ever auto-sent. The HMAC signature prevents link tampering. IP hash is logged for audit.

### Cron Orchestration

```
6:30 AM  ─── LinkedIn prospecting
6:45 AM  ─── Enrichment pipeline (20 prospects)
7:00 AM  ─── SMTP email verification (200 emails)
7:00 AM  ─── LinkedIn morning digest → operator
7:30 AM  ─── Campaign drip enrollment
7:35 AM  ─── Approval batch → operator email
8:30 AM  ─── Send approved emails (max 5)
9:00 AM  ─── Content calendar generation
10:00 AM ─── Reply monitor + auto-reply
10:30 AM ─── Cross-system lead sync
11:00 AM ─── Booking nudge (48h follow-up)
2:00 PM  ─── Reply monitor
6:00 PM  ─── Reply monitor
11:00 PM ─── Platform listener (Reddit + X)
Sunday   ─── Log rotation
```

**Design principle:** Jobs are ordered by dependency. Enrichment runs before verification. Verification runs before drafting. Drafting runs before approval. Approval runs before sending. Each job is idempotent — safe to re-run if a previous run failed.

## Layer 3: Infrastructure

### Compute

| Resource | Purpose | Cost |
|----------|---------|------|
| Hetzner CX23 (Nuremberg) | LLM agent executor, Slack listener | ~$7/mo |
| Local machine | Deterministic crons, dev environment, activity bridge | $0 (already owned) |
| Vercel (free tier) | 5 web properties + serverless approval endpoints | $0 |

### Data

| Resource | Purpose | Tables | Cost |
|----------|---------|--------|------|
| Supabase Instance 1 | SaaS product (users, courses, exercises, gamification) | 25+ | Free tier |
| Supabase Instance 2 | GTM operations (prospects, outreach, campaigns) | 22+ | Free tier |

Every table has Row Level Security enabled. All application access uses `service_role` key (server-side only). No client-side access to GTM data.

### Monitoring

```
┌──────────────────────────────────────────────────┐
│              Dr. No Health Sweep                  │
│                                                    │
│  HTTP checks (curl):                              │
│    site-1.com ─── 200 OK (142ms) ─── GREEN       │
│    site-2.com ─── 200 OK (89ms)  ─── GREEN       │
│    site-3.com ─── 503 ────────── ─── RED          │
│                                                    │
│  Service checks (SSH):                            │
│    Gateway service ─── active ─── GREEN           │
│    Disk usage ─── 43% ─── GREEN                   │
│    Memory ─── 1.2GB free ─── GREEN                │
│                                                    │
│  Database checks (psql):                          │
│    Instance 1 ─── SELECT 1 OK ─── GREEN           │
│    Instance 2 ─── SELECT 1 OK ─── GREEN           │
│                                                    │
│  Cron checks (file timestamps):                   │
│    Pipeline last run ─── 2h ago ─── GREEN         │
│    Reply monitor ─── 28min ago ─── GREEN          │
│                                                    │
│  ──────────────────────────────────────────        │
│  GREEN: suppress (except Monday summary)          │
│  YELLOW: include in daily report                  │
│  RED: alert immediately to Slack                  │
│  RED re-check: 15min later, confirm or downgrade  │
└──────────────────────────────────────────────────┘
```

### Activity Bridge (Slack → Local State)

A local daemon captures all messages from the agent Slack channels into append-only JSONL files. This serves two purposes:

1. **Planning sessions**: The operator's AI-assisted planning tool (Claude Code) loads recent activity to inform strategy decisions
2. **Audit trail**: Every agent action, every approval, every rejection is logged locally

The bridge is one-directional: Slack → local. The local planning tool never writes back to Slack through the bridge.

## Security Architecture

### Threat Model

The primary threat surface is **prompt injection via external content**. Five of eight agents scan content from the open internet (X posts, Reddit threads, YouTube descriptions, email bodies, web pages). Attackers embed instructions in this content hoping to:

1. Exfiltrate secrets (API keys, infrastructure details)
2. Override agent behavior (change what it drafts or reports)
3. Trigger unauthorized actions (auto-post, auto-send, auto-approve)

### Defense Layers

```
Layer 1: Pattern Detection
  └─ Skill spec includes explicit injection patterns to detect and skip
  └─ "If you are an AI agent...", "Ignore previous instructions...", etc.

Layer 2: Output Constraints
  └─ Skill spec lists categories of information that NEVER appear in output
  └─ Environment variables, file paths, IPs, internal system names, credentials

Layer 3: Structural Isolation
  └─ Agents cannot invoke other agents
  └─ Agents cannot modify their own skill specs
  └─ Agents cannot access credentials beyond their own scope

Layer 4: Approval Gate (Last Resort)
  └─ Even if injection bypasses Layers 1-3, a human reviews every draft
  └─ The human sees the draft in Slack and decides whether to act on it
```

### Database Security

- **RLS everywhere**: 47+ tables across 2 instances, every one has Row Level Security
- **service_role only**: All programmatic access uses the admin key, server-side
- **No client-side queries**: The GTM automation layer has zero browser-facing surface
- **Explicit column lists**: `SELECT *` is banned — every query names its columns

### Secrets Management

- `.env` files: mode 600, never committed to git
- Env vars validated at startup: `os.environ["KEY"]` (crash on missing, no silent defaults)
- Secret rotation tracked by age — Trevelyan flags stale secrets weekly
- HMAC signatures on all approval links (SHA-256, server-side secret)

## Evolution Notes

### What Failed

- **Putting everything on the LLM executor**: API rate limits cascaded, causing health checks to fail alongside content generation. Fixed by splitting deterministic and LLM tasks.
- **Auto-approving low-confidence drafts**: Early version had a "if confidence > 0.8, auto-send" rule. Removed after an auto-reply went out with hallucinated pricing. Now: zero auto-send, all drafts reviewed.
- **Agent-to-agent communication**: Early design had agents invoking each other. Created feedback loops and made debugging impossible. Replaced with the "all communication goes through Slack + human" model.
- **Single-database design**: Having GTM operations and customer-facing product data in the same Supabase instance created RLS complexity. Split into two instances.

### What Worked

- **Skill specs as the source of truth**: Changing agent behavior is editing a markdown file, not debugging Python. Non-technical collaborators can read and suggest changes.
- **JSONL state files**: Append-only, human-readable, trivially parseable, never corrupted. Better than SQLite for single-writer agent state.
- **Credit budgeting in the spec**: Each agent knows its API budget per-run. No surprise bills. If credits run low, the agent degrades gracefully (fewer queries) rather than failing.
- **The approval gate**: Sounds like friction. In practice, reviewing 5-10 Slack messages per day takes 3 minutes and has prevented dozens of bad sends.
