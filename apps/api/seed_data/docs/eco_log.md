# Engineering Change Order Log — Warehouse Robot v2

| ECO #   | Date        | Originator | Description                                                       | Affected subsystems    | Status      |
|---------|-------------|------------|-------------------------------------------------------------------|------------------------|-------------|
| ECO-160 | 2026-04-02  | Sarah Chen | Add 0.4mm chamfer to bracket BRK-A1 to remove burr stress riser   | chassis                | implemented |
| ECO-161 | 2026-04-08  | Raj Patel  | Increase trace width on PCB-PWR-2401 gate drive paths             | power, motor_control   | implemented |
| ECO-165 | 2026-04-14  | Mei Tanaka | Approve second source SenseTec for CAM-STEREO                     | sensing, supply_chain  | implemented |
| ECO-168 | 2026-04-21  | Tom Bauer  | Revise motor controller retry count from 5 to 3 (later reverted)  | motor_firmware         | reverted    |
| ECO-170 | 2026-04-28  | Lin Park   | Add IP54 gasket on top cover seam                                 | chassis                | implemented |
| ECO-173 | 2026-05-03  | Priya Iyer | Increase gripper arm link wall by 0.4mm                           | arms, gripper          | implemented |
| ECO-175 | 2026-05-06  | Raj Patel  | Update MD-MOSFET-IRFB part rev to address Vds rating margin       | power                  | implemented |
| ECO-176 | 2026-05-07  | Carlos     | Qualify second source for AL-6063-T5 (preparatory)                | chassis, supply_chain  | implemented |
| ECO-178 | 2026-05-13  | Sarah Chen | Switch BRK-A1 / BRK-A2 high-flux regions to AL-7075-T6            | chassis, supply_chain  | decided     |
| ECO-179 | 2026-05-15  | Tom Bauer  | Add motor controller skip-band 4050–4250 RPM (gripper resonance)  | motor_firmware, gripper| proposed    |

ECO-168 was reverted because reducing retries triggered latched-off motors
during transient overcurrent in DVT thermal cycling (PR #214 restored
behaviour to spec and the latch-off was traced to the bracket thermal
margin issue, not retry count).
