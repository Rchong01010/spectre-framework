#!/usr/bin/env python3
"""Minimal ops health checker — Dr. No pattern.

Zero LLM dependency. Uses curl subprocess for HTTP checks (no urllib
scheme risks), basic service validation, and Slack alerting.

Run via cron: 0 13 * * * python3 health-checker.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# --- Configuration ---

ENDPOINTS = [
    {"name": "main-site", "url": "https://example.com", "timeout": 10, "max_response_ms": 2000},
    {"name": "api", "url": "https://api.example.com/health", "timeout": 10, "max_response_ms": 2000},
    {"name": "dashboard", "url": "https://dashboard.example.com", "timeout": 10, "max_response_ms": 3000},
]

STATE_DIR = Path.home() / ".agent-state"
STATE_FILE = STATE_DIR / "ops-uptime.jsonl"
ALERT_FILE = STATE_DIR / "ops-alerts.jsonl"

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
SLACK_WEBHOOK_PREFIX = "https://hooks.slack.com/"


# --- URL Validation ---


def _validate_https_url(url: str) -> str:
    """Reject non-HTTPS URLs. Prevents file://, ftp://, and other scheme attacks."""
    if not url.startswith("https://"):
        raise ValueError(f"Only https:// URLs allowed, got: {url[:20]}")
    return url


# --- Health Checks ---


def check_http(endpoint: dict) -> dict:
    """Check HTTP endpoint health using curl subprocess.

    Uses curl instead of urllib to avoid file:// scheme risks entirely.
    curl only supports http/https/ftp — and we validate https:// above.
    """
    name = endpoint["name"]
    url = _validate_https_url(endpoint["url"])
    timeout = endpoint["timeout"]
    max_ms = endpoint["max_response_ms"]

    try:
        # curl outputs "HTTP_CODE TOTAL_TIME_SECONDS" via -w format
        result = subprocess.run(
            [
                "curl", "-s", "-o", "/dev/null",
                "-w", "%{http_code} %{time_total}",
                "--max-time", str(timeout),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        parts = result.stdout.strip().split()
        if len(parts) != 2:
            raise ValueError(f"Unexpected curl output: {result.stdout!r}")

        status_code = int(parts[0])
        elapsed_ms = int(float(parts[1]) * 1000)

    except subprocess.TimeoutExpired:
        return {
            "system": name, "status": "RED",
            "http_code": 0, "response_ms": 0,
            "notes": f"Timeout after {timeout}s",
        }
    except Exception as e:
        return {
            "system": name, "status": "RED",
            "http_code": 0, "response_ms": 0,
            "notes": f"Error: {type(e).__name__}: {e}",
        }

    if status_code == 0:
        status = "RED"
        notes = "Connection failed (curl returned 000)"
    elif status_code != 200:
        status = "RED"
        notes = f"HTTP {status_code}"
    elif elapsed_ms > max_ms:
        status = "YELLOW"
        notes = f"Slow response: {elapsed_ms}ms (threshold {max_ms}ms)"
    else:
        status = "GREEN"
        notes = None

    return {
        "system": name,
        "status": status,
        "http_code": status_code,
        "response_ms": elapsed_ms,
        "notes": notes,
    }


def check_cron_freshness(job_name: str, state_file: Path, max_staleness_hours: float) -> dict:
    """Check if a cron job has run recently by checking state file mtime."""
    if not state_file.exists():
        return {
            "system": f"cron:{job_name}",
            "status": "RED",
            "notes": f"State file not found: {state_file.name}",
        }

    mtime = datetime.fromtimestamp(state_file.stat().st_mtime, tz=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600

    if age_hours > max_staleness_hours * 2:
        status = "RED"
    elif age_hours > max_staleness_hours:
        status = "YELLOW"
    else:
        status = "GREEN"

    return {
        "system": f"cron:{job_name}",
        "status": status,
        "last_run_hours_ago": round(age_hours, 1),
        "notes": f"Last run {age_hours:.1f}h ago" if status != "GREEN" else None,
    }


# --- State Tracking ---


def log_state(results: list[dict]):
    """Append health check results to JSONL state file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    with open(STATE_FILE, "a") as f:
        for result in results:
            result["ts"] = ts
            f.write(json.dumps(result) + "\n")


def should_alert(system: str, status: str) -> bool:
    """Check if we should alert (dedup: no re-alert within 4 hours)."""
    if not ALERT_FILE.exists():
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
    with open(ALERT_FILE) as f:
        for line in f:
            entry = json.loads(line)
            if (
                entry.get("system") == system
                and entry.get("status") == status
                and datetime.fromisoformat(entry["ts"]) > cutoff
            ):
                return False
    return True


def record_alert(system: str, status: str):
    """Record that we alerted for dedup purposes."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "system": system,
        "status": status,
        "alerted": True,
    }
    with open(ALERT_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


# --- Alerting ---


def post_to_slack(text: str):
    """Post alert to Slack via incoming webhook using curl. SSRF-guarded."""
    if not SLACK_WEBHOOK_URL:
        print(f"[alert] No SLACK_WEBHOOK_URL set. Message:\n{text}")
        return

    if not SLACK_WEBHOOK_URL.startswith(SLACK_WEBHOOK_PREFIX):
        print("[alert] Refusing non-Slack webhook URL", file=sys.stderr)
        return

    payload = json.dumps({"text": text})
    try:
        subprocess.run(
            [
                "curl", "-s", "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", payload,
                "--max-time", "10",
                SLACK_WEBHOOK_URL,
            ],
            capture_output=True,
            timeout=15,
        )
    except Exception as e:
        print(f"[alert] Slack post failed: {e}")


def format_report(results: list[dict], is_monday: bool = False) -> str | None:
    """Format health check results into a Slack message."""
    issues = [r for r in results if r["status"] != "GREEN"]

    if not issues and not is_monday:
        return None  # Suppress all-green on non-Monday

    lines = []
    if is_monday:
        lines.append("[OPS] Weekly Systems Report")
        lines.append("")
        for r in results:
            status_icon = {"GREEN": "G", "YELLOW": "Y", "RED": "R"}[r["status"]]
            notes_str = f" -- {r['notes']}" if r.get("notes") else ""
            lines.append(f"  {status_icon}  {r['system']}{notes_str}")
    else:
        lines.append("[OPS] Health Check")
        lines.append("")
        for r in issues:
            notes_str = f" -- {r['notes']}" if r.get("notes") else ""
            lines.append(f"  {r['status']}  {r['system']}{notes_str}")

    green = sum(1 for r in results if r["status"] == "GREEN")
    yellow = sum(1 for r in results if r["status"] == "YELLOW")
    red = sum(1 for r in results if r["status"] == "RED")
    lines.append("")
    lines.append(f"Healthy: {green} | Degraded: {yellow} | Down: {red}")

    return "\n".join(lines)


# --- Main ---


def main():
    is_monday = datetime.now().weekday() == 0

    # Run all HTTP checks
    results = [check_http(ep) for ep in ENDPOINTS]

    # Log state
    log_state(results)

    # Format report
    report = format_report(results, is_monday=is_monday)

    # Handle critical alerts (RED = immediate)
    for r in results:
        if r["status"] == "RED" and should_alert(r["system"], "RED"):
            alert = f"[OPS] ALERT -- RED\n\n{r['system']} is DOWN\n{r.get('notes', '')}"
            post_to_slack(alert)
            record_alert(r["system"], "RED")

    # Post regular report
    if report:
        post_to_slack(report)

    # Print summary to stdout (for cron log)
    for r in results:
        status = r["status"]
        ms = r.get("response_ms", "n/a")
        print(f"  {status:6s}  {r['system']:30s}  {ms}ms")


if __name__ == "__main__":
    main()
