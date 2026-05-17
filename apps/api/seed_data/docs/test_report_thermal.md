# Test Report — Thermal Cycling, DVT

**Reference:** TR-THM-DVT-007
**Date:** 2026-05-11 (initial) — 2026-05-15 (re-verification)
**Test engineer:** Lin Park

## 1. Setup

- Chamber: ESS-2400, dual-zone.
- Units under test: 3, 7, 9 (initial). Units 3, 7, 9 plus 11 re-baselined
  post ECO-178.
- Profile: 5 °C → 50 °C ramp at 2 °C/min, 60 min soak each end. 5 cycles
  with 100% rated load applied during high-temp soak.
- Instrumentation: PT100 RTDs on chassis (4), motor mount (2 per motor),
  PCB-PWR-2401 (2), BMS (2). IR camera survey at each soak transition.
- Pass criterion: chassis temp ≤ 85 °C at motor mount under full load.

## 2. Initial results (before ECO-178)

| Cycle | Unit | Peak chassis temp (°C) at motor mount | Pass/Fail |
|-------|------|--------------------------------------|-----------|
| 142   | 7    | 91                                   | FAIL      |
| 138   | 3    | 88                                   | FAIL      |
| 145   | 9    | 86                                   | MARGINAL  |

Failure mode: heat localised to bracket boss face. IR camera confirmed
concentration directly under motor flange. Teardown revealed
discolouration on bracket boss face. Root cause: bracket geometry
conduction-limited under sustained slew.

## 3. Re-verification (post ECO-178)

| Cycle | Unit | Peak chassis temp (°C) at motor mount | Pass/Fail |
|-------|------|--------------------------------------|-----------|
| 142   | 7    | 76                                   | PASS      |
| 142   | 3    | 74                                   | PASS      |
| 142   | 9    | 75                                   | PASS      |
| 142   | 11   | 75                                   | PASS      |

15 °C peak reduction, 9 °C margin to spec. Loop closed for DVT.

## 4. Anomalies observed

- During initial failure, motor driver firmware (pre PR #214) had a
  retry counter off-by-one that intermittently latched motors off when
  overcurrent triggered. Symptom resolved after merge.
- BMS hysteresis behaviour during the post-ECO sweep showed slightly
  wide deassert. Filed as a follow-up; resolved by PR #221.

## 5. Conclusion

Pass. Thermal lane closed for DVT. Recommend re-running this profile
at PVT on the AL-7075-T6 brackets sourced from AlumWest to confirm
material grade behaviour at production tolerance.
