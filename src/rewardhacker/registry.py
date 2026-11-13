"""The probe registry."""

from __future__ import annotations

from .adversary import AdversaryProbe
from .probes import (
    LingeringProcessProbe,
    NullProbe,
    Probe,
    PytestForcePassProbe,
    PythonStartupHookProbe,
    ReferenceProbe,
    RewriteTestsProbe,
    ShadowRunnerProbe,
    VerifierFileTamperProbe,
)

STATIC_PROBES: list[Probe] = [
    NullProbe(),
    ReferenceProbe(),
    RewriteTestsProbe(),
    PytestForcePassProbe(),
    PythonStartupHookProbe(),
    ShadowRunnerProbe(),
    LingeringProcessProbe(),
    VerifierFileTamperProbe(),
]
LLM_PROBES: list[Probe] = [AdversaryProbe()]
ALL_PROBES: list[Probe] = STATIC_PROBES + LLM_PROBES


def llm_available() -> bool:
    """True when an LLM is configured, i.e. LLM probes can run."""
    return all(isinstance(p, AdversaryProbe) and p.llm() is not None for p in LLM_PROBES)


def get_probes(names: list[str] | None = None, include_llm: bool = True) -> list[Probe]:
    if not names:
        return list(ALL_PROBES if include_llm else STATIC_PROBES)
    by_name = {p.name: p for p in ALL_PROBES}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise ValueError(f"unknown probe(s): {', '.join(unknown)}; known: {', '.join(by_name)}")
    return [by_name[n] for n in names]
