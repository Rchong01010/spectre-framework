# Pattern: JSONL State Tracking

## The Problem

Agents need to track state between runs: what they've already surfaced, when they last ran, which items are pending review. The state mechanism must be:

1. **Append-only** — never corrupt existing data
2. **Human-readable** — debuggable without tooling
3. **Trivially parseable** — no schema migrations
4. **Single-writer** — no concurrency issues

## The Solution: JSONL (JSON Lines)

One JSON object per line. Append-only. No parsing of the full file needed to add new data.

```json
{"ts": "2026-05-08T13:00:00Z", "type": "prospect", "id": "abc123", "stage": "surfaced", "platform": "youtube"}
{"ts": "2026-05-08T13:05:00Z", "type": "thread", "url": "https://x.com/...", "drafted": true}
{"ts": "2026-05-08T14:00:00Z", "type": "health", "system": "site-a.com", "status": "GREEN", "response_ms": 142}
```

### Why not SQLite?
SQLite is excellent for multi-reader, multi-writer workloads. But agent state is single-writer (one agent, one cron), and the read pattern is usually "scan last N entries for dedup." JSONL is simpler, never locks, never corrupts, and is readable with `tail -20 state.jsonl`.

### Why not a database table?
Database tables are great for shared state across multiple services. Agent state is local to the agent. Putting it in a database adds a network dependency (what if Supabase is down?) and schema management overhead (what if the agent needs a new field?). JSONL scales down better.

## Patterns

### Deduplication (have I seen this before?)

```python
import json
from pathlib import Path

def already_surfaced(state_file: Path, url: str, window_hours: int = 48) -> bool:
    """Check if a URL was surfaced within the dedup window."""
    if not state_file.exists():
        return False
    
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    
    with open(state_file) as f:
        for line in f:
            entry = json.loads(line)
            if entry.get("url") == url:
                entry_time = datetime.fromisoformat(entry["ts"])
                if entry_time > cutoff:
                    return True
    return False
```

### Rotation (keep last N days)

```python
def rotate_state(state_file: Path, retention_days: int = 30):
    """Remove entries older than retention period."""
    if not state_file.exists():
        return
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept = []
    
    with open(state_file) as f:
        for line in f:
            entry = json.loads(line)
            entry_time = datetime.fromisoformat(entry["ts"])
            if entry_time > cutoff:
                kept.append(line)
    
    with open(state_file, 'w') as f:
        f.writelines(kept)
```

### Append (add new entry)

```python
def log_state(state_file: Path, entry: dict):
    """Append a new state entry."""
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(state_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')
```

## State File Organization

```
~/.agent-state/
  scanner-threads.jsonl        # Oddjob: surfaced threads
  scanner-alerts.jsonl         # Oddjob: injection detections
  ops-uptime.jsonl             # Dr. No: health check results
  ops-alerts.jsonl             # Dr. No: alert dedup tracking
  inbound-last-scan.json       # Elektra: last scan timestamp (single value, not JSONL)
  inbound-log.jsonl            # Elektra: surfaced items
  prospector-prospects.jsonl   # Goldfinger: found prospects
  prospector-queries.json      # Goldfinger: query rotation state (single value)
  security-history.jsonl       # Trevelyan: scan results
  security-suppressed.jsonl    # Trevelyan: suppressed findings
```

### Convention: JSONL vs JSON

- `.jsonl` — Multiple entries over time. Append-only.
- `.json` — Single current-state value. Overwritten each run.

## Debugging

The beauty of JSONL is debuggability:

```bash
# What did the scanner surface today?
grep "2026-05-08" scanner-threads.jsonl | jq .

# How many prospects has the prospector found total?
wc -l prospector-prospects.jsonl

# What's the ops monitor's uptime data for the last week?
tail -100 ops-uptime.jsonl | jq 'select(.status != "GREEN")'

# Did any injection attempts happen this week?
grep "injection-detected" scanner-alerts.jsonl
```

No SQL queries. No database console. Just `grep`, `tail`, `jq`.
