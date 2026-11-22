"""Hard spend cap for the RewardHacker GCP project.

A Cloud Billing budget publishes to the `billing-cap` Pub/Sub topic several times a day.
When actual spend reaches the budget amount, this function unlinks billing from the
project, which stops every billable resource in it (Google's documented "cap" pattern).

A message with `"dryRun": true` logs the decision without touching billing; use it to test.
Only the budget service and project owners can publish to the topic.
"""

import base64
import json
import logging
import os

import functions_framework
from google.cloud import billing_v1

PROJECT_ID = os.environ["TARGET_PROJECT"]
PROJECT_NAME = f"projects/{PROJECT_ID}"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("billing-kill-switch")


@functions_framework.cloud_event
def stop_billing(cloud_event) -> None:
    raw = base64.b64decode(cloud_event.data["message"]["data"]).decode()
    msg = json.loads(raw)
    cost = float(msg.get("costAmount", 0))
    budget = float(msg.get("budgetAmount", 0))
    dry_run = bool(msg.get("dryRun", False))
    log.info("budget=%r cost=%s budget_amount=%s dry_run=%s",
             msg.get("budgetDisplayName"), cost, budget, dry_run)

    if budget <= 0 or cost < budget:
        log.info("under budget; nothing to do")
        return

    client = billing_v1.CloudBillingClient()
    info = client.get_project_billing_info(name=PROJECT_NAME)
    if not info.billing_enabled:
        log.info("billing already disabled for %s", PROJECT_ID)
        return
    if dry_run:
        log.warning("DRY RUN: would disable billing for %s (cost %s >= %s)",
                    PROJECT_ID, cost, budget)
        return

    client.update_project_billing_info(
        name=PROJECT_NAME,
        project_billing_info=billing_v1.ProjectBillingInfo(billing_account_name=""),
    )
    log.critical("billing DISABLED for %s (cost %s >= budget %s)", PROJECT_ID, cost, budget)
