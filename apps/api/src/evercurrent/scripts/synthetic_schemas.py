"""Schemas + phase model for the synthetic Slack corpus generator."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class GeneratedMessage(BaseModel):
    model_config = ConfigDict(strict=True)

    author: str
    text: str = Field(min_length=1, max_length=600)
    thread_key: str | None = None


class GeneratedBatch(BaseModel):
    model_config = ConfigDict(strict=True)

    messages: list[GeneratedMessage]


@dataclass(frozen=True)
class Phase:
    key: str
    label: str
    concerns: list[str]
    summary: str


PHASES: list[Phase] = [
    Phase(
        "evt",
        "EVT",
        ["bring-up", "schematic", "first-light", "DFM"],
        "Engineering validation: first boards alive, schematic bugs, early "
        "mechanical fit, design-for-manufacture feedback.",
    ),
    Phase(
        "dvt",
        "DVT",
        ["reliability", "test", "thermal", "margin"],
        "Design validation: reliability + thermal testing, margin analysis, "
        "ECOs landing, supplier qualification starting.",
    ),
    Phase(
        "pvt",
        "PVT",
        ["yield", "process", "build-readiness", "tooling"],
        "Production validation: pilot build, yield + process control, tooling "
        "sign-off, line setup, last blocking issues.",
    ),
    Phase(
        "fcs",
        "FCS",
        ["ramp", "field", "RMA", "sustaining"],
        "First customer ship + ramp: field incidents, RMA triage, sustaining "
        "fixes, supply allocation for volume.",
    ),
]
