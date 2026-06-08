# BMS Firmware Release Notes — v0.9.2

## Summary

PR #221 lands the BMS hysteresis tighten and the motor controller
retry off-by-one fix. Two changes, both reviewed by Tom and merged
2026-06-05.

## Change 1: hysteresis tighten

The pack cell-balancing hysteresis was widened from 8 C to 5 C. This
brings the balancing decision closer to the actual cell-to-cell
delta and reduces idle current draw by an estimated 18 mA per pack
during balancing windows.

Risk: tighter hysteresis means more frequent balancer engages, which
increases switching noise on the BMS comms bus. Bench tested
overnight at 25 C, no chatter observed. Recommend a second confirm at
hot soak.

## Change 2: motor controller retry off-by-one

The motor controller IO retry loop counted 0 to N inclusive instead
of 0 to N-1, causing one extra retry attempt at the boundary. PR
#214 was the original report. PR #221 lands the fix.

This bug was visible as a 2 percent failure rate on the bench during
the first-spin tests. After the fix, the rate dropped to 0 percent
over 4 hours of soak.

## Affected entities

- Pack 4 firmware image (BMS)
- Motor controller boards rev B and rev C
- DVT exit test plan section 4.2

## Outstanding work

- Confirm hot-soak hysteresis behavior before DVT exit.
- Re-derate the BMS thermal model if the chassis bracket alloy switch
  closes — current model assumes AL-6063.
