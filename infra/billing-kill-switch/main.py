"""Hard spend cap for the RewardHacker GCP project.

A Cloud Billing budget publishes to the `billing-cap` Pub/Sub topic several times a day.
When actual spend reaches the budget amount, this function unlinks billing from the
project, which stops every billable resource in it (Google's documented "cap" pattern).

Messages:
  * budget notifications (from Cloud Billing): act when costAmount >= budgetAmount
  * ``"dryRun": true``: log the decision, never touch billing (manual tests)
  * ``"selfTest": true``: every 6 h from Cloud Scheduler; proves the function runs, can read
    billing, and still holds the permission to unlink it. Logs event=selftest_ok, which an
    absence alert watches. Any failure logs at ERROR, which an email alert watches.

Only the budget service, Cloud Scheduler and project owners can publish to the topic.
"""

import base64
import json
import os

import functions_framework
from google.cloud import billing_v1

PROJECT_ID = os.environ["TARGET_PROJECT"]
PROJECT_NAME = f"projects/{PROJECT_ID}"
UNLINK_PERMISSION = "resourcemanager.projects.deleteBillingAssignment"


def log(severity: str, message: str, **fields) -> None:
    """Structured log line: Cloud Logging reads severity and jsonPayload fields from it."""
    print(json.dumps({"severity": severity, "message": message, **fields}), flush=True)


def can_unlink_billing() -> bool:
    """Ask IAM (without changing anything) whether we still hold the unlink permission."""
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    r = AuthorizedSession(creds).post(
        f"https://cloudresourcemanager.googleapis.com/v1/projects/{PROJECT_ID}:testIamPermissions",
        json={"permissions": [UNLINK_PERMISSION]},
        timeout=20,
    )
    r.raise_for_status()
    return UNLINK_PERMISSION in r.json().get("permissions", [])


@functions_framework.cloud_event
def stop_billing(cloud_event) -> None:
    try:
        _handle(json.loads(base64.b64decode(cloud_event.data["message"]["data"]).decode()))
    except Exception as exc:
        log("ERROR", f"kill switch FAILED: {type(exc).__name__}: {exc}", event="failure")
        raise


def _handle(msg: dict) -> None:
    client = billing_v1.CloudBillingClient()

    if msg.get("selfTest"):
        info = client.get_project_billing_info(name=PROJECT_NAME)
        if not can_unlink_billing():
            log("ERROR", f"self-test: missing {UNLINK_PERMISSION}; kill switch cannot work", event="failure")
            return
        log("INFO", "self-test ok", event="selftest_ok", billing_enabled=info.billing_enabled)
        return

    cost = float(msg.get("costAmount", 0))
    budget = float(msg.get("budgetAmount", 0))
    dry_run = bool(msg.get("dryRun", False))
    log(
        "INFO",
        "budget notification",
        budget_name=msg.get("budgetDisplayName"),
        cost=cost,
        budget=budget,
        dry_run=dry_run,
    )
    if budget <= 0 or cost < budget:
        return

    info = client.get_project_billing_info(name=PROJECT_NAME)
    if not info.billing_enabled:
        log("INFO", f"billing already disabled for {PROJECT_ID}")
        return
    if dry_run:
        log(
            "WARNING",
            f"DRY RUN: would disable billing for {PROJECT_ID} (cost {cost} >= {budget})",
            event="dry_run",
        )
        return

    client.update_project_billing_info(
        name=PROJECT_NAME,
        project_billing_info=billing_v1.ProjectBillingInfo(billing_account_name=""),
    )
    log(
        "CRITICAL",
        f"billing DISABLED for {PROJECT_ID} (cost {cost} >= budget {budget})",
        event="billing_disabled",
    )
