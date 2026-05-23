# SPECTRE: A Solo Operator's AI Agent Fleet

**8 autonomous agents. 1 human operator. Zero employees.**

SPECTRE is the reference architecture behind a real production system that runs a multi-brand business with AI agents handling distribution, security, ops monitoring, inbound detection, content scanning, and prospecting — all coordinated through Slack with human-in-the-loop approval gates.

This isn't a tutorial or a proof-of-concept. This system has been running in production since April 2026, processing thousands of automated decisions daily across multiple repos, multiple deployments, database instances, and a VPS (any provider).

## What's in this repo

This is not source code you clone and run. It's the **architecture, design patterns, and skill specifications** behind a working system — published so you can study and adapt the patterns for your own agent fleet.

```
spectre-framework/
  README.md                          # You are here
  ARCHITECTURE.md                    # Full system design: infrastructure, data flow, decision model
  agents/                            # Sanitized agent skill specifications
    oddjob-scanner.md                #   Multi-platform content scanner (X, Reddit, LinkedIn)
    dr-no-ops.md                     #   Infrastructure health monitoring
    elektra-inbound.md               #   Inbound signal detection (replies, signups, leads)
    goldfinger-prospector.md          #   Creator/prospect sourcing and qualification
    trevelyan-security.md            #   Automated security posture scanning
    janus-scout.md                   #   Market intelligence and job hunting
    scaramanga-content.md            #   Content drafting in operator's voice
    moneypenny-analyst.md            #   Financial/thesis analysis
  patterns/
    approval-gates.md                # Human-in-the-loop: why agents draft, humans decide
    skill-spec-driven-agents.md      # How declarative skill specs replace imperative code
    cron-orchestration.md            # Scheduling strategies: LLM tasks vs deterministic tasks
    prompt-injection-defense.md      # Defending agents that scan untrusted external content
    state-tracking.md                # JSONL state files, deduplication, idempotency
    credit-budgeting.md              # Operating agents on free tiers and API budgets
  examples/
    health-checker.py                # Minimal ops monitor (Dr. No pattern)
    approval-flow.py                 # HMAC-signed approval gate pattern
    scanner-skeleton.py              # Content scanner with injection defense
  diagrams/
    system-overview.svg              # Full system architecture
    agent-decision-flow.svg          # How an agent decides what to surface
    approval-gate-flow.svg           # Draft → Slack → approve/reject → execute
```

## The System at a Glance

```
                    ┌─────────────────────────────────────┐
                    │           OPERATOR (Human)           │
                    │  Reviews Slack → Approves/Rejects    │
                    └──────────────┬──────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │   Slack Channel    │
                         │      #alerts       │
                         └─────────┬─────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
     ┌────────▼───────┐  ┌────────▼───────┐  ┌────────▼───────┐
     │    Oddjob       │  │   Dr. No       │  │   Elektra      │
     │  (Scanner)      │  │  (Ops)         │  │  (Inbound)     │
     │  Configurable   │  │  Configurable  │  │  Configurable  │
     └────────┬───────┘  └────────┬───────┘  └────────┬───────┘
              │                    │                    │
     ┌────────▼───────┐  ┌────────▼───────┐  ┌────────▼───────┐
     │  Goldfinger     │  │  Trevelyan     │  │   Janus        │
     │  (Prospector)   │  │  (Security)    │  │  (Scout)       │
     │  Configurable   │  │  Configurable  │  │  Configurable  │
     └────────┬───────┘  └────────┬───────┘  └────────┬───────┘
              │                    │                    │
     ┌────────▼───────┐  ┌────────▼───────┐
     │  Scaramanga     │  │  Moneypenny    │
     │  (Content)      │  │  (Analyst)     │
     │  On-demand      │  │  On-demand     │
     └────────────────┘  └────────────────┘
```

**Every agent follows the same contract:**
1. Triggered by cron or on-demand invocation
2. Scans its domain (web, APIs, databases, infrastructure)
3. Drafts output in a structured format
4. Posts to Slack — **never acts autonomously**
5. Human reviews and decides

## Core Design Principles

### 1. Agents Draft, Humans Decide

No agent in this system takes irreversible action. Every agent produces **drafts** — reply drafts, health reports, prospect cards, security findings. The human operator reviews in Slack and acts (or doesn't). This isn't a safety compromise; it's a leverage multiplier. The agent does 95% of the work (research, analysis, formatting). The human contributes the 5% that requires judgment.

### 2. Skill Specs Over Code

Each agent is defined by a **skill specification** — a markdown document that declaratively describes what the agent does, when it runs, what it outputs, and what it's not allowed to do. This is more powerful than writing imperative agent code because:
- Non-engineers can read and modify agent behavior
- The spec is the documentation
- Constraints are explicit and auditable
- The same spec can be executed by different LLM backends

### 3. Separation: LLM Tasks vs Deterministic Tasks

Early mistake: putting everything on the LLM executor. Health checks don't need GPT-4. Cron scheduling doesn't need Claude. **Only tasks that require language understanding run on LLM infrastructure.** Everything else runs as plain bash/Python crons. This cut costs 80% and eliminated a class of reliability failures (API rate limits cascading into missed health checks).

### 4. Defense in Depth for External Content

Any agent that scans external content (X posts, Reddit threads, email replies, web pages) is reading **untrusted input** that will contain prompt injection attempts. Every scanner agent has explicit injection defense rules baked into its skill spec. The approval gate is the last line of defense, but it's a fallback — the primary defense is treating all scanned content as adversarial by default.

## Infrastructure

| Component | What | Where |
|-----------|------|-------|
| Agent executor | Runs LLM-dependent agent skills | VPS (any provider) |
| Deterministic crons | Health checks, email pipeline, enrichment | Local machine (crontab) |
| Approval gate | HMAC-signed approve/reject links | Serverless platform |
| Database | Prospect state, outreach logs, analytics | Database instances (RLS enforced) |
| Notification hub | All agent output, human review | Slack workspace |
| Web properties | Production sites | Serverless platform |
| Activity bridge | Captures Slack → local JSONL for planning sessions | Local daemon |

## The GTM Automation Stack

Beyond the agent fleet, the system includes a Python automation script layer handling:

- **Email pipeline**: Prospect enrichment → SMTP verification → AI-drafted personalized outreach → HMAC approval gate → Gmail send → reply classification → auto-reply to interested leads
- **Multi-source enrichment**: IPQS phone/email validation, CourtListener case scoring, OpenCorporates verification, Census market data
- **Content engine**: Platform monitoring (Reddit, X) → AI remix → approval → scheduled publish
- **LinkedIn pipeline**: Automated prospecting → morning digest → DM drafting → status tracking
- **Creator affiliate discovery**: YouTube API → web enrichment → Stripe integration → multi-language outreach
- **System monitoring**: Periodic health sweeps across all services with Slack alerts

All orchestrated through crontab with scheduled jobs.

## Security Posture

Security isn't an afterthought — it's been through **multiple formal audit rounds** including a full 3-layer assessment (code scan + infrastructure red team + live perimeter testing):

- All database tables with Row Level Security enforced
- Prompt injection defense across all agents scanning external content
- HMAC-signed approval flows (no unsigned actions)
- CRLF sanitization on all email fields
- SSRF guards on outbound HTTP
- Semgrep static analysis + dependency scanning (automated weekly via Trevelyan)
- `.env` files mode 600, never tracked in git

## Who This Is For

- **Solo operators** who want to understand how one person can run a multi-product business with AI agents
- **AI engineers** studying production agent architectures (not toy examples)
- **Hiring managers** evaluating whether someone has actually built and operated agent systems (yes — this is also a portfolio piece, and I'm not going to pretend otherwise)
- **Security engineers** interested in prompt injection defense patterns for autonomous agents

## Who Built This

Reid Chong — solo operator running a multi-brand portfolio (SaaS, e-commerce, education) with AI agents as the workforce. Former enterprise sales (Weave, Workfront, Bugcrowd), 3 years building AI-native companies, 4 years across 3 continents.

- Portfolio: [reidchong.com](https://reidchong.com)
- Product: [claude-academy.com](https://claude-academy.com)
- LinkedIn: [linkedin.com/in/reid-chong07](https://linkedin.com/in/reid-chong07)

## License

MIT. Use these patterns however you want. If you build something cool with them, I'd love to hear about it.
