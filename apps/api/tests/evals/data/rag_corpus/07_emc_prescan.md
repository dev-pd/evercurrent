# EMC Pre-Scan Plan

## Goal

Run an internal EMC pre-scan on rev C of the main PCB before the
external compliance scan. Catch any obvious radiated emissions issues
in-house first, save calendar time on the external pass.

## Setup

- Chamber: internal screened room, calibrated 2026-04.
- Equipment under test: rev C main PCB, BMS firmware v0.9.2, motor
  controller rev B.
- Source noise candidate: the buck converter (LMR16030) and the
  motor controller switching node.

## Test matrix

| Mode               | Frequency range | Expected pass |
|--------------------|-----------------|---------------|
| Idle               | 30 MHz - 1 GHz  | yes           |
| Motor driving      | 30 MHz - 1 GHz  | yes (with 6 dB margin) |
| BMS balancing      | 150 kHz - 30 MHz | yes (with 3 dB margin) |
| Hot soak (45 C)    | 30 MHz - 1 GHz  | yes           |

## Scheduling concern

The lab raised the question of moving the pre-scan from week 7 to
week 6. Lab availability is tight. Raj is investigating whether the
schedule shift is feasible without colliding with the firmware
hysteresis confirm.

## Decisions

- We will go with the Texas Instruments LMR16030 buck converter for
  rev C. Lower BOM, qualified part, in stock. The risk is the
  switching node EMC profile, mitigated by the layout review and
  the pre-scan plan above.
- We are skipping the optional secondary fuse on rev C. Procurement
  headache, low marginal safety gain.
