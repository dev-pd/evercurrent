# Supplier Strategy — Aluminum Sourcing Q2 2026

## Active suppliers

| Supplier      | Material      | Status        |
|---------------|---------------|---------------|
| ExtruCo       | AL-6063-T5    | On strike     |
| AlumWest      | AL-7075-T6    | Active, PPAP pending |
| PrecisionCoat | finishing     | Qualified for AL-7075 |

## Current disruption

ExtruCo confirmed a labor strike on 2026-06-05. AL-6063-T5 extrusion
is stuck at three weeks of remaining inventory. Resumption date is
unknown.

We are pulling AlumWest forward as the backup supplier on AL-7075-T6.
Per ECO-178 the bracket BRK-A1 design has switched to AL-7075-T6
anyway, so the disruption forces us to accept a cost premium of
12 percent on the bracket line for the next batch.

## AlumWest readiness

AlumWest can start extrusion on Monday 2026-06-09. First article
inspection cleared on 2026-06-08 with all dimensions within +/- 0.07
mm against +/- 0.10 mm spec. PPAP submission has not started yet and
must be scheduled within two weeks.

## Risk register

- If ExtruCo strike extends past the next sprint, AlumWest will be
  asked to take both extrusion and finishing. We have no second
  source qualified for that combination.
- If we ship before AlumWest PPAP is complete we are out of process
  on the supplier qualification gate.
- PrecisionCoat is approved only for AL-7075 finishing. If we revert
  to AL-6063 for any reason, finishing capacity becomes a gap.

## Decisions taken

- Accept 12 percent cost premium on BRK-A1 batch.
- Add explicit PPAP milestone before DVT exit.
- Continue to monitor ExtruCo for a return-to-work date.
