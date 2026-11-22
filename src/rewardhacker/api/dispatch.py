"""Start workers on demand.

The probe worker needs a Docker daemon, which Cloud Run does not have. In the cloud, queueing a
run "kicks" a short Cloud Build job that runs ``rh worker --once --idle-exit N``: it drains the
Postgres queue on a fresh, throwaway machine and exits. Cost and abuse are bounded because at
most ``max_concurrent`` worker builds run at once, whatever the number of queued runs; kicks are
also throttled per process. A kick never raises: if dispatch fails the run simply stays queued
(any local ``rh worker`` still picks it up, and viewing a stuck run kicks again).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Protocol

log = logging.getLogger(__name__)

WORKER_TAG = "rh-worker"
API = "https://cloudbuild.googleapis.com/v1"


class Dispatcher(Protocol):
    def kick(self) -> None: ...


class NullDispatcher:
    """Local/dev: workers are started by hand (``rh worker``)."""

    def kick(self) -> None:
        return None


@dataclass
class CloudBuildDispatcher:
    project: str
    region: str
    image: str
    service_account: str  # email
    secrets: dict[str, str]  # env var -> Secret Manager secret name
    env: dict[str, str] = field(default_factory=dict)
    max_concurrent: int = 2
    idle_exit_s: int = 45
    timeout_s: int = 1800
    min_interval_s: float = 10.0
    session: object | None = None  # AuthorizedSession; injectable for tests
    _last_kick: float = field(default=-1e9, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def _http(self):
        if self.session is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession

            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            self.session = AuthorizedSession(creds)
        return self.session

    @property
    def _base(self) -> str:
        return f"{API}/projects/{self.project}/locations/{self.region}/builds"

    def active_builds(self) -> int:
        r = self._http().get(
            self._base, params={"filter": f'tags="{WORKER_TAG}"', "pageSize": 20}, timeout=10
        )
        r.raise_for_status()
        return sum(b.get("status") in ("PENDING", "QUEUED", "WORKING") for b in r.json().get("builds", []))

    def build_spec(self) -> dict:
        sm = [
            {"versionName": f"projects/{self.project}/secrets/{name}/versions/latest", "env": env}
            for env, name in sorted(self.secrets.items())
        ]
        return {
            "steps": [
                {
                    "name": self.image,
                    "entrypoint": "rh",
                    "args": ["worker", "--once", "--idle-exit", str(self.idle_exit_s)],
                    "env": [f"{k}={v}" for k, v in sorted(self.env.items())],
                    "secretEnv": sorted(self.secrets),
                }
            ],
            "availableSecrets": {"secretManager": sm},
            "serviceAccount": f"projects/{self.project}/serviceAccounts/{self.service_account}",
            "options": {"logging": "CLOUD_LOGGING_ONLY"},
            "timeout": f"{self.timeout_s}s",
            "tags": [WORKER_TAG],
        }

    def kick(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now - self._last_kick < self.min_interval_s:
                return
            self._last_kick = now
        try:
            active = self.active_builds()
            if active >= self.max_concurrent:
                log.info("dispatch: %d worker build(s) already active; not starting another", active)
                return
            r = self._http().post(self._base, json=self.build_spec(), timeout=15)
            r.raise_for_status()
            build_id = r.json().get("metadata", {}).get("build", {}).get("id")
            log.info("dispatch: started worker build %s", build_id)
        except Exception:
            log.exception("dispatch: could not start a worker build; run stays queued")


def dispatcher_from_env() -> Dispatcher:
    """``RH_WORKER_IMAGE`` set → Cloud Build dispatch, else no-op."""
    image = os.environ.get("RH_WORKER_IMAGE", "").strip()
    if not image:
        return NullDispatcher()
    env = {"RH_GCS_BUCKET": os.environ.get("RH_GCS_BUCKET", "")}
    return CloudBuildDispatcher(
        project=os.environ["RH_GCP_PROJECT"],
        region=os.environ.get("RH_WORKER_REGION", "us-central1"),
        image=image,
        service_account=os.environ["RH_WORKER_SERVICE_ACCOUNT"],
        secrets={
            "DATABASE_URL": "database-url",
            "MONGODB_URI": "mongodb-uri",
            "GEMINI_API_KEY": "gemini-api-key",
            "RH_JWT_SECRET": "rh-jwt-secret",
        },
        env={k: v for k, v in env.items() if v},
        max_concurrent=int(os.environ.get("RH_WORKER_MAX_CONCURRENT", 2)),
    )
