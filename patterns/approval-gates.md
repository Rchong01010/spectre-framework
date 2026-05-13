# Pattern: Human-in-the-Loop Approval Gates

## The Problem

Autonomous agents making irreversible decisions will eventually make a wrong one. An auto-sent email with hallucinated pricing. An auto-posted reply to the wrong thread. An auto-approved prospect who turns out to be a competitor.

The question isn't "will it happen" but "when it happens, how much damage does it do?"

## The Solution

Every agent in the system produces **drafts**, never final actions. A human reviews each draft and explicitly approves or rejects it.

```
Agent generates draft
        │
        ▼
Draft posted to Slack
        │
        ▼
Human reviews in Slack
        │
   ┌────┴────┐
   │         │
Approve    Reject
   │         │
   ▼         ▼
Execute   Archive
```

## Implementation Patterns

### Pattern 1: Slack Review (Simple)

Agent posts a formatted draft to a Slack channel. Human reads it, copies the text, and acts manually (posts to X, sends an email, etc.).

**Best for:** Content drafts, reply drafts, prospect cards
**Overhead:** ~2 seconds per draft (read + copy-paste)

### Pattern 2: HMAC-Signed Approval Links (Structured)

For workflows where the approval triggers a downstream action (like sending an email):

1. Agent generates draft, stores it in DB with status `pending_approval`
2. System emails operator with two links: Approve and Skip
3. Links contain HMAC signatures (SHA-256) preventing tampering
4. Clicking Approve hits a serverless function that:
   - Verifies the HMAC signature
   - Updates DB status to `approved`
   - Logs IP hash + timestamp for audit
5. Next cron cycle picks up `approved` items and executes

```python
import hmac
import hashlib
import os

def generate_approval_url(item_id: str, action: str) -> str:
    secret = os.environ["APPROVAL_HMAC_SECRET"]
    payload = f"{item_id}:{action}"
    signature = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    base_url = os.environ["APPROVAL_ENDPOINT"]
    return f"{base_url}?id={item_id}&action={action}&sig={signature}"
```

**Best for:** Email sends, outreach approvals, any action with consequences
**Overhead:** One click per item

### Pattern 3: Batch Review

For high-volume workflows, batch multiple items into a single review:

```
[APPROVAL] 5 emails ready for review

1. Prospect A — "Subject: AI workflow audit for your team"
   [Approve] [Skip] [Edit]

2. Prospect B — "Subject: Quick question about your AI stack"
   [Approve] [Skip] [Edit]
...
```

**Best for:** Email campaigns, bulk outreach
**Overhead:** ~30 seconds for 5 items

## Why This Works

### It's not actually slow
Reviewing 5-10 Slack messages takes 3 minutes per day. That's the "cost" of human oversight. In exchange:
- Zero hallucinated sends
- Zero wrong-recipient errors  
- Zero off-brand replies
- Full audit trail of every approval

### It catches real problems
From production experience:
- An auto-reply draft that included hallucinated pricing → caught and fixed
- A prospect card for someone who was actually a competitor → caught and rejected
- A content draft that accidentally mentioned an internal system name → caught and edited

### The agent does 95% of the work
The human isn't doing the research, drafting, formatting, or scheduling. The agent handles all of that. The human contributes the 5% that requires judgment: "yes this is good" or "no, fix this."

## Anti-Patterns

### "Auto-approve if confidence > 0.8"
Tried this. It works 99% of the time. The 1% causes damage that takes hours to fix. Not worth it.

### "Auto-approve after N hours with no response"
This turns the approval gate into an opt-out gate. The operator goes on a hike, comes back to 15 auto-sent emails. Never auto-escalate.

### "Let the agent decide if it needs approval"
The agent can't evaluate its own judgment. That's the whole point of having a human in the loop. The approval gate is not conditional.
