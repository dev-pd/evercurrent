# Product Requirements — Warehouse Robot v2

## 1. Overview

Warehouse Robot v2 is the next generation of our autonomous goods-moving robot
intended for medium-sized fulfillment centers (5,000–25,000 m²). It improves
on v1 in payload, run time, and serviceability while maintaining the same
footprint.

## 2. User stories

- **Operations lead:** "I can deploy a new robot in under 30 minutes from
  unboxing to first mission."
- **Picker:** "The robot pauses cleanly when I cross its path and resumes
  automatically when I'm clear."
- **Maintenance technician:** "I can swap a battery pack in under 90 seconds
  without tools."

## 3. Performance targets

| Parameter           | Target                      | Notes                            |
|---------------------|-----------------------------|----------------------------------|
| Payload             | 30 kg sustained, 45 kg peak | Doubles v1 sustained payload.    |
| Top speed           | 1.8 m/s                     | Loaded.                          |
| Run time            | 8 hours                     | Mixed duty cycle.                |
| Charge time         | 90 minutes                  | 0 -> 80% on AC fast-charger.     |
| Continuous yield    | ≥ 98% per shift             |                                  |
| Acoustic emission   | ≤ 62 dB(A) at 1m            | Per indoor warehouse spec.       |
| Operating temp      | 5–40 °C ambient             | Storage -10 to 50 °C.            |
| IP rating           | IP54                        | Splash + dust resistant.         |

## 4. Key specifications

### Drive

- Motor M-2401, 24V BLDC, peak torque 12 Nm, sustained 8 Nm.
- Motor controller MD-MOSFET-IRFB on PCB-PWR-2401 (power board).
- Wheelbase 540 mm, differential drive.

### Chassis

- AL-6063-T5 primary structure (see ECO-178 for revised material in
  high-flux regions: AL-7075-T6).
- Total mass without payload: 28 kg target, 30 kg max.
- Thermal budget: chassis temp under continuous load ≤ 85 °C.

### Power

- Battery pack: 6S BC-18650 cells, 24V nominal, 30Ah usable.
- BMS supports active balancing, thermal protect with hysteresis (post-ECO:
  5 °C deassert, see firmware PR #221).

### Sensing

- LiDAR x1 (front-facing).
- Stereo camera, 60 fps.
- IMU 6-axis.

## 5. Compliance

- UL 3300 for service robots.
- FCC Part 15 Class A (industrial).
- EU machinery directive 2006/42/EC.

## 6. Non-goals (v2)

- Outdoor operation.
- Stair climbing.
- Manipulation beyond bin-pick (use the arm option in v2.5).
