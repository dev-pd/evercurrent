# DVT Exit Test Plan

## Gate criteria

To exit DVT and enter PVT the following must be true:

1. All P0 cycling tests pass at the chassis temperature spec of 85 C.
2. The bracket alloy on BRK-A1 is documented in BOM rev C.
3. AlumWest PPAP submission is scheduled.
4. BMS thermal model re-run against the closing bracket alloy.
5. Motor controller bench test passes at 4 hours of soak with zero
   retries.

## P0 tests added this cycle

- Thermal soak at 85 C for 4 hours on the BRK-A1 bracket as fabricated
  by AlumWest. Pass criteria: no plastic deformation, no measurable
  drift in mounting-hole position.
- Hot hysteresis confirm on BMS firmware v0.9.2. Pass criteria: no
  chatter on the comms bus over 1 hour at 45 C.
- Drop test on rev C chassis at 1 m. Pass criteria: no cracking at
  bracket boss face.

## Owners

| Test                      | Owner          |
|---------------------------|----------------|
| Thermal soak              | Lin Wong (qa)  |
| Hot hysteresis            | Tom Reyes (fw) |
| Drop test                 | Lin Wong (qa)  |
| Bench motor soak          | Tom Reyes (fw) |
| BMS thermal re-derate     | Tom Reyes (fw) |

## Schedule

- Thermal soak: Friday 2026-06-12 afternoon, bench 3.
- Hot hysteresis: Monday 2026-06-15 morning.
- Drop test: Wednesday 2026-06-17.
- Bench motor soak: in progress, completes 2026-06-09 evening.

## Known risks against the gate

- AlumWest material may not be on-site in time for the thermal soak.
- If ExtruCo strike extends, the gate may slip by one week.
- If the BMS thermal model fails the re-run, the gate fails and we
  return to chassis bracket geometry options instead of alloy switch.
