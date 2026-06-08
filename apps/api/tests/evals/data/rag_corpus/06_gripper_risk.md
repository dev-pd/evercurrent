# Gripper Resonance Risk — Cross-Subsystem

## Observed signal

Three independent mentions over the last two days in the mech-design
and electrical channels point to a resonance band on the gripper arm
at approximately 4150 RPM. The frequency overlaps with the rated
torque spec on the motor mount that the chassis team owns.

## Why it is a risk

The gripper is owned by Priya. The motor mount is owned by Sarah.
Neither has formally connected the two specs. If the system spends
time at 4150 RPM during the planned task profile, the motor mount may
see torque transients beyond the documented limit.

The mount is the subject of ECO-178, which is changing the bracket
alloy nearby. The mount spec itself is unchanged but the thermal
behavior of the surrounding material may slightly shift the mount's
operating envelope.

## Cross-references

- PR #221 references the motor controller retry behavior near the
  same operating point.
- The thermal report flags an uptick in anomaly count on the cycle
  that included this RPM band.

## Recommended action

1. Sarah to confirm the motor-mount torque spec against the gripper
   load profile at 4150 RPM.
2. Priya to characterize the gripper resonance band width.
3. Tom to confirm the motor controller has no oscillation at this
   point after PR #221.
4. Add a watchpoint to the DVT exit checklist.
