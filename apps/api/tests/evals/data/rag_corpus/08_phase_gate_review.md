# Phase Gate Review — Friday 2026-06-12

## Agenda

David owns the slide deck. The review covers the gate criteria to
move from DVT into PVT.

1. ECO-178 status (10 min) — Sarah
2. Supplier sourcing (10 min) — Mei
3. Firmware v0.9.2 readiness (10 min) — Tom
4. Test plan additions (10 min) — Lin
5. Risk register update (15 min) — David
6. Decision and gate close (15 min) — all

## Open decisions to close at the review

- Accept AlumWest as the primary BRK-A1 supplier despite PPAP being
  outstanding, with the constraint that PPAP must close in two weeks.
- Add explicit thermal soak test to the DVT exit gate.
- Accept the 12 percent cost premium on the BRK-A1 line.
- Confirm BMS hysteresis at 5 C passes hot soak.

## Open risks

- ExtruCo strike. If unresolved by gate review, the gate may slip a
  week.
- Gripper resonance band overlap with motor mount torque spec.
  Cross-subsystem risk, tracked separately.
- BMS thermal model invalidated by the bracket alloy change. Re-run
  must complete before the gate.

## Required attendees

- David Park (pm)
- Sarah Chen (mech)
- Raj Patel (ee)
- Tom Reyes (fw)
- Lin Wong (qa)
- Mei Tanaka (supply)
