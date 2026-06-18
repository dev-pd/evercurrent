"""Canonical Atlas-v2 cast: the people whose Slack chatter drives the demo.

Single source of truth for personas — used by the synthetic message generator
and the seed/chatter scripts. eng_role + owned_subsystems mirror the
org_memberships columns so provisioning lines up after backfill.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Persona:
    name: str
    eng_role: str
    emoji: str
    voice: str
    owned_subsystems: list[str] = field(default_factory=list)
    home_channels: list[str] = field(default_factory=list)


# A small cross-functional cast (ee / mech / fw / program / supply) — kept tight
# so a demo workspace stays legible. Add more here to widen the synthetic chatter.
PERSONAS: list[Persona] = [
    Persona(
        "Mei Chen",
        "ee",
        ":zap:",
        "battery + power lead; precise, numbers-first, flags margins early",
        ["power", "1V8_rail", "3V3_buck", "4S2P", "BMS"],
        ["electrical", "general"],
    ),
    Persona(
        "Raj Patel",
        "fw",
        ":computer:",
        "firmware lead; release-notes voice, OTA + power_management",
        ["firmware", "power_management", "hardware_rev", "BMS", "OTA"],
        ["firmware", "general"],
    ),
    Persona(
        "Priya Nair",
        "em",
        ":dart:",
        "program manager; schedule-first, phase gates, FCS risk, decisions",
        ["schedule", "FCS", "DVT", "phase_gate"],
        ["general", "compliance"],
    ),
    Persona(
        "Tom Alvarez",
        "supply",
        ":package:",
        "supply chain; lead-times, POs, alloy + cell sourcing, vendor quotes",
        ["AlumWest", "ECO-178", "lead_time", "PO"],
        ["supply-chain", "manufacturing"],
    ),
]

BY_NAME: dict[str, Persona] = {p.name: p for p in PERSONAS}


def personas_for_channel(channel_name: str) -> list[Persona]:
    name = channel_name.lower()
    matched = [p for p in PERSONAS if any(h in name for h in p.home_channels)]
    return matched or PERSONAS
