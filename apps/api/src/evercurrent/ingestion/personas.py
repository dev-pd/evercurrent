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


PERSONAS: list[Persona] = [
    Persona(
        "Mei Chen", "ee", ":zap:",
        "battery + power lead; precise, numbers-first, flags margins early",
        ["power", "1V8_rail", "3V3_buck", "4S2P", "BMS"],
        ["electrical", "general"],
    ),
    Persona(
        "Dana Wu", "ee", ":battery:",
        "power electronics; pragmatic, talks regulators, rails, EMI",
        ["3V3_buck", "1V8_rail", "EMI", "regulator"],
        ["electrical"],
    ),
    Persona(
        "Lin Zhao", "mech", ":wrench:",
        "chassis + enclosure; references ECOs and drawings, tolerance-minded",
        ["chassis", "actuator_mount", "BRK-A1", "AL-7075-T6"],
        ["mech-design", "general"],
    ),
    Persona(
        "Nina Petrov", "mech", ":gear:",
        "thermal + mechanical; worries about heat paths and stack-up",
        ["thermal", "heatsink", "enclosure", "gasket"],
        ["mech-design"],
    ),
    Persona(
        "Raj Patel", "fw", ":computer:",
        "firmware lead; release-notes voice, OTA + power_management",
        ["firmware", "power_management", "hardware_rev", "BMS", "OTA"],
        ["firmware", "general"],
    ),
    Persona(
        "Omar Haddad", "fw", ":satellite:",
        "embedded + radio; terse, talks drivers, duty cycle, timing",
        ["radio", "driver", "duty_cycle", "ADC"],
        ["firmware"],
    ),
    Persona(
        "Sara Kim", "qa", ":test_tube:",
        "test + reliability; gatekeeper tone, blocks on data, cites HTOL/drop",
        ["thermal", "reliability", "ADC", "HTOL"],
        ["qa-testing", "general"],
    ),
    Persona(
        "Carlos Reyes", "qa", ":mag:",
        "reliability engineering; failure-analysis voice, cycles + RMAs",
        ["reliability", "FA", "cycles", "RMA"],
        ["qa-testing"],
    ),
    Persona(
        "Tom Alvarez", "supply", ":package:",
        "supply chain; lead-times, POs, alloy + cell sourcing, vendor quotes",
        ["AlumWest", "ECO-178", "lead_time", "PO"],
        ["supply-chain", "manufacturing"],
    ),
    Persona(
        "Yuki Tanaka", "supply", ":truck:",
        "procurement + logistics; allocation, MOQ, freight, vendor risk",
        ["MOQ", "allocation", "freight", "vendor"],
        ["supply-chain"],
    ),
    Persona(
        "Priya Nair", "em", ":dart:",
        "program manager; schedule-first, phase gates, FCS risk, decisions",
        ["schedule", "FCS", "DVT", "phase_gate"],
        ["general", "compliance"],
    ),
    Persona(
        "Ben Foster", "design", ":triangular_ruler:",
        "industrial design; CMF, ergonomics, asks about fit and finish",
        ["CMF", "ergonomics", "industrial_design"],
        ["mech-design", "general"],
    ),
]

BY_NAME: dict[str, Persona] = {p.name: p for p in PERSONAS}


def personas_for_channel(channel_name: str) -> list[Persona]:
    name = channel_name.lower()
    matched = [p for p in PERSONAS if any(h in name for h in p.home_channels)]
    return matched or PERSONAS
