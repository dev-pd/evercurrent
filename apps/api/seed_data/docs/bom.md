# Bill of Materials — Warehouse Robot v2 (DVT)

Snapshot as of 2026-05-10. ECO-178 (AL-7075-T6 in two bracket regions) is
approved but not yet reflected in line BOM until kit batch 11.

| Part #         | Description                              | Qty | Vendor (primary) | Lead time | Unit cost (USD) | Notes                                  |
|----------------|------------------------------------------|-----|------------------|-----------|-----------------|----------------------------------------|
| M-2401         | 24V BLDC motor, 12 Nm peak               | 2   | MotorCorp        | 5 wks     | 142.00          | DC sourced, qualified                  |
| MD-MOSFET-IRFB | Motor driver MOSFET, IRFB style          | 4   | InfineonDist     | 3 wks     | 4.20            |                                         |
| PCB-PWR-2401   | Power board assembly                     | 1   | InternalAsm      | 2 wks     | 88.00           | In-house assembly                      |
| BC-18650       | Li-ion 18650 cell, 3.5Ah                 | 24  | CellCo           | 6 wks     | 6.80            | v2 chemistry                           |
| BMS-2401       | Battery management system PCB            | 1   | InternalAsm      | 2 wks     | 64.00           | Firmware PR #221 ships with rev D      |
| AL-6063-T5     | Aluminum extrusion bar stock, 6m         | -   | ExtruCo          | 3 wks     | 28.00/m         | **Strike risk** — see ECO-178          |
| AL-7075-T6     | Aluminum extrusion, high-strength        | -   | AlumWest         | 4 wks     | 34.50/m         | New per ECO-178, finishing TBD         |
| BRK-A1         | Chassis motor mount bracket              | 2   | MachineHaus      | 3 wks     | 22.00           | Rev C per ECO-178                      |
| BRK-A2         | Chassis frame bracket, mid               | 4   | MachineHaus      | 3 wks     | 18.00           |                                         |
| ARM-LINK-1     | Gripper arm link, lower                  | 1   | MachineHaus      | 3 wks     | 41.00           |                                         |
| ARM-LINK-2     | Gripper arm link, upper                  | 1   | MachineHaus      | 3 wks     | 41.00           |                                         |
| GRIPPER-MOTOR  | Gripper drive motor                      | 1   | MotorCorp        | 5 wks     | 96.00           | Resonance @ 4150 RPM (firmware skip)   |
| LIDAR-F1       | Front-facing LiDAR module                | 1   | SenseTec         | 8 wks     | 480.00          | Long lead — keep buffer                |
| CAM-STEREO     | Stereo camera assembly                   | 1   | SenseTec         | 4 wks     | 220.00          |                                         |
| IMU-6X         | 6-axis IMU                               | 1   | InfineonDist     | 2 wks     | 12.00           |                                         |
| ENC-MOTOR      | Motor encoder, optical                   | 2   | SenseTec         | 4 wks     | 38.00           |                                         |
| WHL-FRONT      | Front drive wheel, polyurethane          | 2   | RubberCorp       | 2 wks     | 18.00           |                                         |
| WHL-CASTER     | Rear caster, swivel                      | 2   | RubberCorp       | 2 wks     | 14.00           |                                         |
| HARN-MAIN      | Main wire harness                        | 1   | HarnessCo        | 4 wks     | 72.00           |                                         |
| CHASSIS-COVER  | Top + side covers, sheet steel           | 1   | MachineHaus      | 3 wks     | 54.00           | IP54-sealed                            |

Total ~ $1,820 BOM cost per unit at DVT volumes. Target cost at MP volume:
$1,250 (cost-down roadmap in `docs/PRODUCTION_ROADMAP.md`).
