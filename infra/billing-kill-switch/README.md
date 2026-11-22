# Billing kill switch

Hard spend cap for the `rewardhacker` GCP project. GCP budgets only alert, so:

```
budget "rewardhacker-kill-switch" (all services, ₹150/month)
  └─> Pub/Sub topic billing-cap
        └─> Cloud Run function billing-kill-switch (this folder)
              └─> cost >= budget → unlink billing from the project
```

Unlinking billing stops every billable resource in the project (the site goes down); it does
not touch other projects. Re-enable in the console under Billing → Account management.

A separate console-created **spend cap** (`RewardHackerBudgetCap`, Cloud Run only, ₹150) is a
second line of defence for the one service Google's native caps support.

## Least-privilege service account

`billing-kill-switch@rewardhacker.iam.gserviceaccount.com`:

| Role | Why |
|---|---|
| `roles/billing.projectManager` | unlink billing (`deleteBillingAssignment`) |
| `roles/browser` | read billing status (`resourcemanager.projects.get`) |
| `roles/run.invoker`, `roles/eventarc.eventReceiver`, `roles/serviceusage.serviceUsageConsumer` | Eventarc trigger |

## Deploy

```powershell
gcloud functions deploy billing-kill-switch --gen2 --region=us-central1 --runtime=python312 `
  --source=infra/billing-kill-switch --entry-point=stop_billing --trigger-topic=billing-cap `
  --service-account=billing-kill-switch@rewardhacker.iam.gserviceaccount.com `
  --trigger-service-account=billing-kill-switch@rewardhacker.iam.gserviceaccount.com `
  --set-env-vars=TARGET_PROJECT=rewardhacker --memory=256Mi --max-instances=1
```

## Test (safe)

A message with `"dryRun": true` logs the decision without touching billing:

```powershell
gcloud pubsub topics publish billing-cap --message='{\"costAmount\":200,\"budgetAmount\":150,\"dryRun\":true}'
gcloud functions logs read billing-kill-switch --gen2 --region=us-central1 --limit=5
# → DRY RUN: would disable billing for rewardhacker (cost 200.0 >= 150.0)
```

The real unlink path has not been exercised (doing so would take the project offline).

## How you find out it failed (monitoring)

| Layer | What | Fires when |
|---|---|---|
| Error alert | log alert "Billing kill switch: error or billing disabled" → owner email | the function logs ERROR (it could not cap spend) or CRITICAL (it disabled billing) |
| Self-test | Cloud Scheduler `kill-switch-selftest`, every 6 h, publishes `{"selfTest": true}`; the function reads billing and asks IAM (`testIamPermissions`) whether it still holds `deleteBillingAssignment` | a failed self-test logs ERROR → error alert |
| Dead-man's switch | log metric `kill_switch_selftest_ok` + absence alert "self-test missing" | no successful self-test for 13 h (function, trigger, topic or scheduler broken) |
| Independent | budget emails at 50/90/100 % from Cloud Billing itself | spend crosses ₹75/135/150; a 100 % email while the site is still up = the switch failed |

Alerting is free until at least 2027-09-01, then ~$0.35/condition/month.
The scheduler's service agent needs `roles/pubsub.publisher` on `billing-cap` (granted).
