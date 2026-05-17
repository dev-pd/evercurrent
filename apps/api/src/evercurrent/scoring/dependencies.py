"""Cross-functional dependency matching.

Fuzzy match between a user's owned subsystems / parts and the entities
extracted from a message. Lowercase + substring + a small synonym map.
Pure function so it can be exercised directly in evals.
"""

from __future__ import annotations

from collections.abc import Iterable

SYNONYMS: dict[str, set[str]] = {
    "aluminum extrusion": {"AL-6063-T5", "AL-7075-T6", "AL-6063", "AL-7075", "extrusion"},
    "extrusion": {"AL-6063-T5", "AL-7075-T6", "AL-6063", "AL-7075", "aluminum extrusion"},
    "chassis": {"BRK-A1", "BRK-A2", "bracket", "mounting"},
    "bracket": {"BRK-A1", "BRK-A2", "chassis"},
    "power": {"PCB-PWR-2401", "BMS", "MD-MOSFET", "MOSFET", "battery", "BC-18650"},
    "motor_control": {"MD-MOSFET", "M-2401", "motor driver"},
    "BMS": {"BMS-2401", "battery", "BC-18650"},
    "gripper": {"GRIPPER-MOTOR", "ARM-LINK-1", "ARM-LINK-2", "gripper-motor"},
    "arms": {"ARM-LINK-1", "ARM-LINK-2"},
    "BOM": {"AL-6063-T5", "AL-7075-T6", "BC-18650", "M-2401", "supplier"},
}


def _normalise(value: str) -> str:
    return value.strip().lower().replace("_", " ")


def _expand(name: str) -> set[str]:
    normalised = _normalise(name)
    base = {normalised}
    for key, synonyms in SYNONYMS.items():
        if _normalise(key) == normalised:
            base.update(_normalise(s) for s in synonyms)
    return base


def dependency_match(
    entities: Iterable[str],
    owned_subsystems: Iterable[str],
    owned_parts: Iterable[str],
) -> bool:
    """Return True if any owned subsystem/part matches any entity (fuzzy)."""
    ents_norm = [_normalise(e) for e in entities]
    if not ents_norm:
        return False
    owned: set[str] = set()
    for s in owned_subsystems:
        owned.update(_expand(s))
    for p in owned_parts:
        owned.update(_expand(p))
    return any(o in ents_norm or any(o in e or e in o for e in ents_norm) for o in owned)
