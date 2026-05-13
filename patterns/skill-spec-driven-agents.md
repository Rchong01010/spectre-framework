# Pattern: Skill-Spec-Driven Agents

## The Problem

Traditional agent development means writing Python/TypeScript code that defines agent behavior. This creates several issues:

1. **Non-engineers can't read or modify agent behavior.** Changing what an agent does requires a developer.
2. **The documentation is always out of date.** The code is the truth, but the code is hard to read.
3. **Constraints are implicit.** "Don't auto-send" lives in a `if not auto_approve:` branch that someone might delete.
4. **Testing is hard.** You need to run the whole agent to verify behavior changes.

## The Solution

Define each agent as a **skill specification** — a markdown document that declaratively describes:

- What the agent does
- When it runs (trigger)
- What it outputs (format)
- What it's NOT allowed to do (hard rules)
- How much it can spend (credit budget)
- How it tracks state (dedup, JSONL)

The LLM executor reads the spec and follows it. The spec IS the code.

## Anatomy of a Skill Spec

```markdown
# Skill: Agent Name

## Purpose
One paragraph: what this agent does and why.

## Trigger
When the agent runs (cron schedule, on-demand, event-driven).

## Output channel
Where results are posted (Slack channel, email, file).

## Output format
Exact template of what the output looks like.
Include examples with realistic data.

## What it checks / searches / monitors
Detailed list of data sources and methods.
Be specific: "curl -s -o /dev/null -w ..." not "check HTTP status."

## Engagement filters / qualification criteria
Rules for what gets surfaced vs. skipped.
ALL criteria must be met (AND logic, not OR).

## Prompt injection defense
Explicit patterns to detect and skip.
Explicit categories of information to never include in output.

## Approval gate
HARD RULE: what the agent is NOT allowed to do.
Always stated as "never" — not "usually" or "unless."

## Credit budget
Per-run limit. What to do if credits are low.
Graceful degradation, not failure.

## State tracking
What state file format (JSONL recommended).
Retention policy (e.g., 30 days, then rotate).

## Deduplication
How to avoid re-surfacing the same item.
Check both Slack history and local state.
```

## Why Specs Beat Code

### 1. Readable by anyone
A product manager, a marketing lead, or a non-technical founder can read a skill spec and understand exactly what the agent does. They can suggest changes in the same format.

### 2. The spec IS the documentation
There's no drift between "what the agent does" and "what the docs say." The spec is both.

### 3. Constraints are explicit and auditable
"HARD RULE: Never post to X" is visible in the spec. It's not buried in a conditional branch. An auditor can read every agent's constraints in 10 minutes.

### 4. Backend-agnostic
The same spec can be executed by:
- OpenAI Codex on a VPS
- Claude Code locally
- A custom Python executor
- A future agent runtime that doesn't exist yet

The spec describes WHAT, not HOW. The executor handles HOW.

### 5. Version-controlled behavior changes
Changing agent behavior = editing a markdown file and committing. Git diff shows exactly what changed. Code review is trivial.

## Anti-Patterns

### Specs that say "use your best judgment"
The whole point of a spec is to remove judgment calls from the agent. If the agent needs judgment, the spec isn't detailed enough.

### Specs without credit budgets
Agents without spending limits will drain API credits during edge cases (retry loops, broad searches). Always cap per-run spend.

### Specs without output format examples
An agent that "reports findings" without a defined format will produce inconsistent output. The operator can't scan it quickly. Define the exact format with realistic examples.

### Specs that reference other specs
"See Goldfinger spec for qualification criteria." This creates coupling and makes specs harder to audit independently. Each spec should be self-contained.
