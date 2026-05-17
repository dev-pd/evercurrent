# Test Report — Drop Test, DVT

**Reference:** TR-DRP-DVT-004
**Date:** 2026-05-12
**Test engineer:** Lin Park

## 1. Setup

- Drop tower: standardised 0–2.0 m configurable.
- Surfaces: smooth concrete; smooth concrete plus 12mm steel plate
  (worst-case impact transfer).
- Profile: 1.2 m and 1.5 m drops, six orientations each (top, bottom,
  four sides).
- Instrumentation: high-speed camera 1500 fps, accelerometer on chassis,
  post-drop teardown.
- Pass criterion: no functional regression in drive/sense after drop;
  no structural cracks penetrating to mounting interfaces; minor
  cosmetic damage acceptable.

## 2. Results

| Unit | Drop height | Surface     | Orientation | Pass/Fail | Notes                                       |
|------|-------------|-------------|-------------|-----------|---------------------------------------------|
| 1    | 1.2 m       | concrete    | bottom      | PASS      | Caster scuff. No structural impact.         |
| 1    | 1.5 m       | concrete    | bottom      | PASS      | Caster scuff. Cover deformation 0.4mm.      |
| 4    | 1.2 m       | concrete+pl | side-left   | PASS      | Witness mark at BRK-A1 boss face.           |
| 4    | 1.5 m       | concrete+pl | side-left   | PASS      | Witness mark identical region, no fracture. |
| 5    | 1.5 m       | concrete+pl | front       | PASS      | Front cover cosmetic chip, no penetration.  |

## 3. Notable findings

The bracket region witnessing repeated impact marks is the same
region that failed thermally (TR-THM-DVT-007). Two failure modes
converging on the same part validated the prioritisation of ECO-178.

No drives or sensors regressed in any tested unit.

## 4. Conclusion

Pass. Drop test lane is green for DVT. ECO-178 brackets (AL-7075-T6
in high-flux regions) are expected to behave at least as well as the
baseline brackets under impact due to higher yield strength; will
re-verify on the post-ECO units in the next campaign.
