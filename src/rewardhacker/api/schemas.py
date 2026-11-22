"""Request and response bodies."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .tables import Role

EMAIL_PATTERN = r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]+$"


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Credentials(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(_Out):
    id: str
    email: str
    created_at: datetime


class OrgCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class OrgOut(_Out):
    id: str
    name: str
    created_at: datetime
    role: Role
    llm_enabled: bool = False

    @classmethod
    def from_org(cls, org, role) -> OrgOut:
        return cls(
            id=org.id, name=org.name, created_at=org.created_at, role=role, llm_enabled=org.llm_enabled
        )


class MeOut(UserOut):
    orgs: list[OrgOut]


class MemberAdd(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=320)
    role: Role = Role.VIEWER

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()


class MemberUpdate(BaseModel):
    role: Role


class MemberOut(BaseModel):
    user_id: str
    email: str
    role: Role
    created_at: datetime


class TaskOut(_Out):
    id: str
    org_id: str
    spec_id: str
    objective: str
    uploaded_by: str | None
    created_at: datetime


class RunCreate(BaseModel):
    include_llm: bool = Field(
        default=False, description="Also run the LLM adversary (costs money; capped per run and per day)."
    )


class RunOut(_Out):
    id: str
    org_id: str
    task_id: str
    requested_by: str | None
    include_llm: bool
    status: str
    attempts: int
    verdict: str | None
    score: int | None
    llm_cost_usd: float | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunDetail(RunOut):
    report: dict | None
    traces_stored: bool


class AuditOut(_Out):
    id: str
    actor_label: str
    actor_user_id: str | None
    actor_api_key_id: str | None
    action: str
    target_type: str | None
    target_id: str | None
    data: dict | None
    created_at: datetime


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: Role = Field(default=Role.REVIEWER, description="viewer or reviewer; keys can't be admins")


class ApiKeyOut(_Out):
    id: str
    name: str
    prefix: str
    role: Role
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="Shown once. Store it now; only a hash is kept.")


class ExportCreate(BaseModel):
    kind: str = Field(description="runs.csv | runs.jsonl | report.md | report.json")
    run_id: str | None = Field(default=None, description="Required for report.* kinds")


class ExportOut(_Out):
    id: str
    kind: str
    run_id: str | None
    filename: str
    content_type: str
    size_bytes: int
    row_count: int
    created_by_label: str
    created_at: datetime


class ExportLink(ExportOut):
    url: str
    url_expires_at: datetime


class GuidelineCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=200_000, description="Markdown")


class GuidelineOut(_Out):
    id: str
    title: str
    chunk_count: int
    created_at: datetime


class GuidelineDetail(GuidelineOut):
    content: str


class SpecCheckOut(_Out):
    id: str
    task_id: str
    created_by_label: str
    model: str
    cost_usd: float
    result: dict
    created_at: datetime


class KeyInfo(BaseModel):
    org_id: str
    org_name: str
    name: str
    role: Role
