#!/usr/bin/env python3
"""HMAC-signed approval gate pattern.

Generates tamper-proof Approve/Skip links for draft content.
The operator clicks a link, which hits a serverless endpoint that
verifies the signature before updating the database.

This is the core pattern behind "agents draft, humans decide."
"""

import hashlib
import hmac
import os
import time
from urllib.parse import urlencode


def generate_approval_urls(
    item_id: str,
    endpoint_base: str,
    hmac_secret: str,
    expiry_seconds: int = 86400,
) -> dict[str, str]:
    """Generate HMAC-signed approve and skip URLs for an item.

    Args:
        item_id: Unique identifier for the draft item
        endpoint_base: Base URL of the approval endpoint (e.g., https://app.com/api/approve)
        hmac_secret: Shared secret for signing
        expiry_seconds: Link validity window (default 24h)

    Returns:
        Dict with 'approve' and 'skip' URLs
    """
    expires_at = int(time.time()) + expiry_seconds
    urls = {}

    for action in ("approve", "skip"):
        # Payload: item_id + action + expiry timestamp
        payload = f"{item_id}:{action}:{expires_at}"
        signature = hmac.new(
            hmac_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        params = urlencode({
            "id": item_id,
            "action": action,
            "expires": expires_at,
            "sig": signature,
        })
        urls[action] = f"{endpoint_base}?{params}"

    return urls


def verify_approval_request(
    item_id: str,
    action: str,
    expires_at: int,
    signature: str,
    hmac_secret: str,
) -> tuple[bool, str]:
    """Verify an incoming approval request.

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check expiry
    if int(time.time()) > expires_at:
        return False, "Link expired"

    # Check action is valid
    if action not in ("approve", "skip"):
        return False, f"Invalid action: {action}"

    # Verify HMAC signature
    payload = f"{item_id}:{action}:{expires_at}"
    expected_sig = hmac.new(
        hmac_secret.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        return False, "Invalid signature"

    return True, ""


def format_approval_email(
    item_id: str,
    draft_subject: str,
    draft_body_preview: str,
    approve_url: str,
    skip_url: str,
) -> str:
    """Format an approval email with the draft preview and action links.

    In production, this would be sent via Gmail API or similar.
    """
    return f"""Subject: [APPROVE] {draft_subject}

Draft email ready for review:

To: <recipient>
Subject: {draft_subject}

---
{draft_body_preview[:500]}
---

Actions:
  APPROVE: {approve_url}
  SKIP:    {skip_url}

This link expires in 24 hours. If no action is taken, the draft stays in pending_approval.
"""


# --- Example Usage ---


if __name__ == "__main__":
    # In production, this comes from env
    HMAC_SECRET = os.environ.get("APPROVAL_HMAC_SECRET", "example-secret-change-me")
    ENDPOINT = "https://your-app.vercel.app/api/approve"

    # Generate approval URLs for a draft
    urls = generate_approval_urls(
        item_id="draft-001",
        endpoint_base=ENDPOINT,
        hmac_secret=HMAC_SECRET,
    )

    print("Generated approval URLs:")
    print(f"  Approve: {urls['approve']}")
    print(f"  Skip:    {urls['skip']}")
    print()

    # Simulate verifying an incoming approval click
    # (In production, this runs in the serverless function)
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(urls["approve"])
    params = parse_qs(parsed.query)

    is_valid, error = verify_approval_request(
        item_id=params["id"][0],
        action=params["action"][0],
        expires_at=int(params["expires"][0]),
        signature=params["sig"][0],
        hmac_secret=HMAC_SECRET,
    )

    print(f"Verification result: valid={is_valid}, error={error!r}")

    if is_valid:
        print("\nNext steps in production:")
        print("  1. Update database: SET status = 'approved' WHERE id = 'draft-001'")
        print("  2. Log: approval_received_at, IP hash")
        print("  3. Next cron cycle picks up approved item and executes")
