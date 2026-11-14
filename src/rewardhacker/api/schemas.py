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
