# Deployment (GCP)

```
GitHub push to main ──CI (lint, tests, LoopBench, web build)──► deploy job
   │  keyless: GitHub OIDC → Workload Identity Federation → rh-deployer
   ▼
Artifact Registry  api:<sha>, worker:<sha>
   ▼
Cloud Run "rewardhacker"  (API + dashboard, 0–1 instances)   ── smoke test: /api/health commit == sha
   │  queue a run → Cloud Build job (worker:<sha>, rh-worker SA) → `rh worker --once`
   ▼                                                            └─ rollback to previous revision on failure
Neon Postgres (queue + data) · MongoDB Atlas (traces, guidelines, spend ledger) · GCS (bundles, exports)
```

| Piece | Where | Notes |
|---|---|---|
| API + dashboard | Cloud Run `rewardhacker`, us-central1 | one origin; `RH_WEB_DIR=/app/web` |
| Workers | Cloud Build (default pool, e2-standard-2) | one build per burst of runs; ≤2 concurrent; free tier 2,500 min/month |
| Images | Artifact Registry `rewardhacker` | cleanup policy keeps the 2 newest per image |
| Files | `gs://rewardhacker-data-289475076247` | `tasks/` (zips), `exports/` (deleted after 7 days) |
| Secrets | Secret Manager | `database-url`, `mongodb-uri`, `gemini-api-key`, `rh-jwt-secret` |
| Spend cap | `infra/billing-kill-switch/` | ₹150 budget → unlink billing; monitored |

## Service accounts (least privilege)

| Account | Can |
|---|---|
| `rh-api` (Cloud Run) | read/write the bucket, read the 4 secrets, start builds, act as `rh-worker`, sign blobs as itself (export URLs) |
| `rh-worker` (Cloud Build) | read the bucket, read the 4 secrets, write logs, pull images |
| `rh-deployer` (GitHub Actions) | push images, deploy new revisions of this one service, act as `rh-api`; only from `main` of this repo |
| `billing-kill-switch` | read billing info, unlink billing from this project |

## Manual deploy (same steps as CI)

```bash
IMAGES=us-central1-docker.pkg.dev/rewardhacker/rewardhacker; SHA=$(git rev-parse HEAD)
docker build --target worker -t $IMAGES/worker:$SHA . && docker build -t $IMAGES/api:$SHA .
docker push $IMAGES/worker:$SHA && docker push $IMAGES/api:$SHA
gcloud run deploy rewardhacker --region=us-central1 --image=$IMAGES/api:$SHA \
  --update-env-vars=RH_WORKER_IMAGE=$IMAGES/worker:$SHA,RH_GIT_SHA=$SHA
```

Rollback: `gcloud run services update-traffic rewardhacker --region=us-central1 --to-revisions=<rev>=100`.
