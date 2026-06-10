"""Post hardware-team demo messages into a real Slack workspace.

Run from the repo root:

    SLACK_DEMO_BOT_TOKEN=xoxb-... uv run --project apps/api \
        python -m apps.api.seed_data.slack_seed

The script will:
1. Ensure each channel exists (creates if missing).
2. Join the bot to each channel.
3. Post the seed corpus.

Required bot scopes: `chat:write`, `channels:manage`,
`channels:join`, `channels:read`.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any, Final, cast

import structlog

from evercurrent.connectors.slack.client import SlackAPIError, SlackClient

log = structlog.get_logger(__name__)

POST_DELAY_SECONDS: Final[float] = 0.2
CHANNELS: Final[tuple[str, ...]] = (
    "mech-design",
    "qa-testing",
    "supply-chain",
    "electrical",
    "firmware",
    "compliance",
    "manufacturing",
    "general",
)


@dataclass(frozen=True)
class SeedMessage:
    channel: str
    author: str
    icon_url: str
    text: str


def _avatar(seed: str) -> str:
    """Stable, real-looking avatar from pravatar.cc keyed by seed."""
    return f"https://i.pravatar.cc/200?u={seed}"


SARAH = ("Sarah Chen", _avatar("sarah-mech"))
LIN = ("Lin Park", _avatar("lin-qa"))
MEI = ("Mei Tanaka", _avatar("mei-supply"))
DAN = ("Dan Okafor", _avatar("dan-elec"))
PRIYA = ("Priya Iyer", _avatar("priya-fw"))
TOM = ("Tom Reilly", _avatar("tom-compliance"))
ANNA = ("Anna Volkov", _avatar("anna-mfg"))
RAJ = ("Raj Mehta", _avatar("raj-pm"))
KARTHIK = ("Karthik Rao", _avatar("karthik-test"))
ELENA = ("Elena Rossi", _avatar("elena-mech-b"))
JAMES = ("James Williams", _avatar("james-elec-b"))
NORA = ("Nora Kim", _avatar("nora-pm-b"))


SEED_CORPUS: tuple[SeedMessage, ...] = (
    # ====================================================================
    # PHASE: EVT bring-up (week 1 — first prototypes back from CM)
    # ====================================================================
    SeedMessage("#general", *RAJ, text=(
        "Team — EVT1 units landed at the lab last night. 12 units total. "
        "Goal this week: full bring-up, identify show-stoppers, get debug "
        "data feeding the DVT plan. Standup at 10 daily."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "First mech inspection on EVT1: 9/12 chassis pass dim check, 3 "
        "have a 0.18mm gap at the lid seam. Tooling drift on the front "
        "extrusion. Mei — flagging to ExtruCo, can we get an SPC pull from "
        "their last run?"
    )),
    SeedMessage("#electrical", *DAN, text=(
        "EVT1 power-on: 10/12 boot. Two boards latch high on the 1V8 rail "
        "and brown out the SoC. Probing the buck — looks like a soldering "
        "issue at L7, not a design fault. Will swap inductors on those two."
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "Bootloader sig check is failing on units with serial < EVT1-005. "
        "Turns out the CM flashed an older `boot_v0.8.2` rather than 0.8.4. "
        "Sending the correct image + flash script to Anna. Should be a "
        "5-minute reflash per unit."
    )),
    SeedMessage("#manufacturing", *ANNA, text=(
        "Got the reflash script from Priya. Working through the 4 affected "
        "units. Also — CM flagged a soldering paste viscosity issue on the "
        "Friday shift. Yield was 92% (target 96%). Investigating with their "
        "process eng. Will report after the next build."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "EVT1 thermal soak started on 8 healthy units this morning. 4h at "
        "55°C ambient, full load. Logging every 30s. Initial data looks "
        "clean. Will share results tomorrow AM."
    )),

    # ====================================================================
    # PHASE: EVT debug (week 2 — issues discovered, decisions queued)
    # ====================================================================
    SeedMessage("#qa-testing", *LIN, text=(
        "Thermal results in: hotspot on the regulator near U7 reads 94°C, "
        "spec is 85°C. All 8 units. This is a design issue, not a unit-to-"
        "unit thing. Dan — pulling you in. Logs in `data/evt1/thermal/`."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "Confirmed. The 3V3 buck is under-spec for our actual load "
        "(measured 1.4A vs designed 1.0A). Options: bigger inductor + "
        "different IC (board respin), or add a copper pour + thermal pad "
        "(stickier ECO but no respin). Leaning toward the latter for DVT. "
        "Cost delta is negligible."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "If Dan goes with the copper pour route I need 0.6mm extra Z "
        "clearance under the regulator. Looking at the chassis — we have "
        "0.4mm today. Two options: bump the standoff height (mech ECO), or "
        "thin the heat spreader pad. I'll model both."
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "Found the cause of the OTA pause issue Anna saw on EVT1-007. "
        "Race condition between the watchdog and the flash unlock. PR up: "
        "`fw#412`. Will land in fw 0.9.0 by EOW. Adds ~150ms to OTA but "
        "guarantees no bricking."
    )),
    SeedMessage("#general", *RAJ, text=(
        "Status going into week 3:\n"
        "• Mech: lid seam tooling fix in flight w/ ExtruCo\n"
        "• Electrical: regulator thermal — ECO route TBD by Fri\n"
        "• Firmware: OTA race fix landing in 0.9.0\n"
        "• Manufacturing: paste viscosity root-caused, fixed\n"
        "Blocker for DVT plan: pick a regulator path. Dan owns by Fri."
    )),

    # ====================================================================
    # PHASE: DVT prep (week 3 — vendor risk, ECOs, plan freeze)
    # ====================================================================
    SeedMessage("#supply-chain", *MEI, text=(
        "Heads up — ExtruCo just notified us of a labor action vote "
        "Monday. Worst case is a 2-3 week strike right when we need our "
        "DVT lot. Pulling AlumWest forward as a second-source. Need a "
        "tolerance trial lot by next Monday — Lin, can you cycle a thermal "
        "pass on the trial parts?"
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "ECO-178 (chassis rib stiffness) looks unaffected by the AlumWest "
        "swap from my side. Modulus delta is inside the envelope we sized "
        "to. Holding the design release on the swap result."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "Booking the thermal chamber for Sat AM to run the AlumWest trial "
        "lot. Will publish FAI numbers by EOD Sat. Holding off on sign-off "
        "until then."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "Heads up — if AlumWest CTE shifts more than 5% we'll need to "
        "revisit the rib pitch on ECO-178. Watching Lin's numbers."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "Decision: going with the copper pour + thermal pad route for the "
        "regulator. Cheaper, no respin, validated on bench. ECO-181 filed. "
        "Sarah — confirming standoff bump on your side."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "Confirmed standoff bump 0.4 → 1.0mm. ECO-179 (mech) filed and "
        "linked to ECO-181 (elec). Releasing CAD package to Anna for the "
        "DVT build."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "AlumWest FAI cleared at +2.1% CTE. Inside the rib pitch envelope. "
        "Signing off on the swap. ECO-178 stays on track."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "Thanks Lin — releasing ECO-178 to manufacturing. Closing the loop "
        "on the AlumWest swap risk."
    )),
    SeedMessage("#general", *RAJ, text=(
        "DVT plan locked. Build start: T+10 days. 50 units, 4 SKUs. ECOs "
        "in scope: 178 (rib), 179 (standoff), 181 (regulator pour). "
        "Firmware target: 0.9.0. Compliance pre-scan: Tom owns. Drop test: "
        "Lin scheduling with Element Test Labs."
    )),

    # ====================================================================
    # PHASE: DVT execution (week 4 — test results pour in)
    # ====================================================================
    SeedMessage("#manufacturing", *ANNA, text=(
        "DVT build day 1 complete. 48/50 units passing E-test. The 2 "
        "failures are connector reseats — not a design issue. CM yield "
        "97.4%, above target. AOI flagged 3 boards for review on the "
        "regulator pour — coverage looks good but they want eyes."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "DVT thermal re-test: U7 regulator now reads 78°C peak under same "
        "load. 7°C below spec, 16°C improvement from EVT1. ECO-181 doing "
        "its job. Logs in `data/dvt/thermal_2026-05-29.csv`."
    )),
    SeedMessage("#compliance", *TOM, text=(
        "Pre-scan EMC results in: Class B compliant on radiated emissions "
        "(margin 4dB on the 800MHz band, tight but passing). Conducted "
        "emissions clean. We're good for the formal scan in week 6. Full "
        "report uploaded to /drive/Compliance/DVT/."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "Drop test results from Element: 1.0m drop, 6 orientations, 5 "
        "units. 4/5 pass fully. 1 unit lost the side cover clip on the "
        "edge-down drop. Sarah — clip geometry might need a tweak."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "Looking at the drop video — the clip lever arm is too long. Easy "
        "fix in CAD, adds 0.5g per unit. ECO-184 going up. Lin, can we get "
        "a re-test on 3 units once tooling is updated?"
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "DVT firmware burn complete on all units. Boot times: avg 1.2s "
        "(target 2.0s). OTA tested on 10 units, all clean. Power profile: "
        "idle 42mW (target 50). Shipping fw 0.9.0 as the DVT baseline."
    )),

    # ====================================================================
    # PHASE: PVT readiness (week 5 — tooling, cost, sign-offs)
    # ====================================================================
    SeedMessage("#supply-chain", *MEI, text=(
        "BOM cost review for PVT: we're at $138.40/unit, target was $135. "
        "$3.40 over. Biggest deltas: regulator IC ($0.80), AlumWest "
        "premium ($1.20), the new standoff hardware ($0.60). Looking at "
        "negotiating the regulator price now that we know volume."
    )),
    SeedMessage("#manufacturing", *ANNA, text=(
        "CM ran a tooling check for PVT scale (10k units/month). Two issues:\n"
        "1. Lid press fixture wears at ~3k cycles — they want a hardened "
        "tool, $8k one-time, 1 week lead.\n"
        "2. Our solder paste mask has insufficient relief on the regulator "
        "pour — bridging risk at speed. ECO-185 needed on the stencil."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "ECO-185 (stencil relief) — I can spin the change today. 0.1mm "
        "additional clearance, no functional impact. Anna, I'll get you a "
        "DXF by EOD."
    )),
    SeedMessage("#compliance", *TOM, text=(
        "Formal EMC scan booked at Bay Area Compliance Labs for Wed of "
        "week 6. Pre-scan margins held in two re-runs this week. FCC ID "
        "application drafted, will file after passing the formal scan."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "ECO-184 (clip) re-test complete. 5/5 units pass 1.0m drop in all "
        "6 orientations. Side cover clip retention now nominal. Sarah's "
        "fix verified. Closing the drop-test risk."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "Late finding — discovered a 200ns glitch on the I2C bus when the "
        "BLE radio TX-fires at full power. Doesn't cause functional fail "
        "today (sensor reads still pass CRC) but it's outside spec. "
        "Investigating. May need a small filter cap. Tracking as RISK-22."
    )),

    # ====================================================================
    # PHASE: Manufacturing handoff (week 6 — final certs, customer)
    # ====================================================================
    SeedMessage("#compliance", *TOM, text=(
        "Formal EMC scan: PASS. Radiated emissions 5dB margin on the worst "
        "band (better than pre-scan). Conducted clean. CE pre-test also "
        "clean. We are cert-ready for FCC + CE. Submitting paperwork "
        "Friday."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "RISK-22 update: 22pF cap on SDA pulls the glitch under 50ns, well "
        "inside I2C spec. ECO-187 to add the cap. Anna — is this safe to "
        "land in the first PVT build, or do we cut a separate rev?"
    )),
    SeedMessage("#manufacturing", *ANNA, text=(
        "Dan — safe to land in PVT1. The stencil is being re-cut for "
        "ECO-185 anyway, we can roll ECO-187 in. No schedule impact. PVT "
        "build start still on track for Monday week 7."
    )),
    SeedMessage("#general", *RAJ, text=(
        "Customer call this morning: they're moving their launch window "
        "forward by 3 weeks. New target FCS: Sep 15. That means we need "
        "to compress PVT → MP by ~2 weeks. Working a revised plan, will "
        "share by Wed. Quick: any phase-gate concerns from each function?"
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "Raj — QA's concern with compression: reliability test (HTOL) is "
        "1000 hours minimum, can't shorten that. If we start the reli "
        "build today we land at Sep 12, 3-day margin. Tight but doable. "
        "Need the reli units off the PVT line, not a separate run."
    )),
    SeedMessage("#supply-chain", *MEI, text=(
        "Compressed schedule risk on my side: AlumWest lead time is 4 "
        "weeks. For MP volume we need to issue the PO this week, not in "
        "two weeks like the original plan. Need a sign-off from Raj + Tom "
        "(spend authorization)."
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "FW side is fine on the compressed plan. 0.9.0 is the PVT "
        "baseline. We'd cut 1.0.0 (release) by end of week 7. No new "
        "features, just hardening + the cert-time bug fixes."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "Mech is the cleanest — no open ECOs after 184/185. Standing by "
        "for the PVT build. Sep 15 FCS is fine on my side."
    )),
    SeedMessage("#general", *RAJ, text=(
        "Decision: compressing to Sep 15 FCS. Authorizing AlumWest MP PO "
        "today (Mei). HTOL starts off the PVT line as Lin requested. "
        "Customer notified, contract amendment in flight. Thanks team — "
        "going to be a hectic 6 weeks."
    )),

    # ====================================================================
    # PHASE: PVT build + early-life issues (week 7-8)
    # ====================================================================
    SeedMessage("#manufacturing", *ANNA, text=(
        "PVT build day 3 update — 142/150 units passing FCT. The 8 "
        "failures cluster on the new I2C cap ECO-187: footprint pads are "
        "slightly off-centre on the stencil v2. Reworking by hand for now. "
        "Stencil v3 ordered, 4-day lead."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "PVT reliability run kicked off this morning. 30 units in HTOL, 30 "
        "in temp cycling, 30 spare. First 24h checkpoint clean. "
        "Dashboard at `data/pvt/reli/`. Will report daily."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "Bench test on 3 PVT units: SDA glitch is *gone* with the 22pF cap. "
        "Margin 18dB on signal integrity scan. ECO-187 validated. Lin, "
        "anything you need from me for the formal sign-off?"
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "Dan — just the eye diagram screenshot from the bench scope, plus "
        "a one-pager linking measured vs spec. I'll attach to the FAI doc."
    )),
    SeedMessage("#supply-chain", *MEI, text=(
        "AlumWest PO confirmed at 25k units, $1.18/each. Final BOM cost "
        "lands at $137.95 (vs $138.40 target after early Apr re-est). "
        "First MP delivery committed for Aug 12. Risk reduced."
    )),

    # ====================================================================
    # PHASE: MP ramp + field beta (week 9-10)
    # ====================================================================
    SeedMessage("#manufacturing", *ANNA, text=(
        "MP ramp day 1: 480/500 units passing all stations. 96% yield, "
        "above our 94% target. Two fails on the lid press (returning to "
        "the hardened tool decision from week 5 — paying off). Six fails "
        "on a new I2C signal noise check — investigating with Dan."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "Anna — pulling the failed boards. The noise check is firing on "
        "boards where the BLE radio antenna trace is too close to a power "
        "via. Looks like a layout marginality, not all boards exhibit. "
        "Investigating whether this is a real failure or a too-tight test "
        "limit. Update by EOD."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "HTOL day 7 checkpoint: all 30 units operational. No degradation "
        "on key parameters (regulator droop, BLE TX power, sensor accuracy). "
        "Temp cycling: 1 unit failed on cycle 142 — visible delamination "
        "on the lid bond line. Sending to FA."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "Lin — the temp cycle fail is concerning. 142 cycles is well "
        "below our spec (500). I'll grab the FA report when ready. Could "
        "be the adhesive batch — Anna, can you pull the lot code for that "
        "unit?"
    )),
    SeedMessage("#manufacturing", *ANNA, text=(
        "Sarah — that unit was built with adhesive lot AC-2401-09. We've "
        "got 480 units in MP using that lot. Suspending until FA closes. "
        "Switching to lot AC-2401-11 for tomorrow's build."
    )),
    SeedMessage("#general", *RAJ, text=(
        "Active issues going into customer beta:\n"
        "1. Adhesive lot AC-2401-09 — 1 unit delamination at 142 cycles, "
        "FA pending (Lin owns)\n"
        "2. BLE antenna proximity — 6 boards failing tighter signal check, "
        "investigating real vs spec (Dan)\n"
        "3. Stencil v3 in flight (no impact, just hand-rework cost)\n"
        "Beta units ship Friday assuming items 1 and 2 close green."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "Adhesive FA in: it's a surface prep issue at CM, not the adhesive "
        "itself. Their isopropyl wipe step was being skipped on that "
        "lot's build. Process eng confirmed corrective action — adding "
        "wipe verification to the SOP. Releasing the 480 units after "
        "re-screen (24-cycle stress)."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "BLE antenna investigation — confirmed false positive. The test "
        "limit was set 6dB tighter than the actual spec. Updating the "
        "test station. Recovered all 6 boards. Lessons learned filed."
    )),
    SeedMessage("#general", *RAJ, text=(
        "Customer beta units shipped today. 50 units to 10 lead customers, "
        "8-week field trial. We'll get weekly telemetry + a customer "
        "review at week 4 and week 8. Big milestone — thanks all."
    )),

    # ====================================================================
    # PHASE: Field telemetry + V2 planning (week 11-13)
    # ====================================================================
    SeedMessage("#firmware", *PRIYA, text=(
        "Week 1 beta telemetry rolling in. 47/50 units checking in daily. "
        "3 silent — likely WiFi config issues at customer site, debugging "
        "with two of them. Battery life trending: avg 22 days vs spec 21. "
        "OTA distribution: 100% on 1.0.0."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "Beta week 2 incident report:\n"
        "• 1 unit returned, customer says \"powers on then dies after 10s\". "
        "Bench replication shows brown-out on the 1V8 rail under cold "
        "start (sub-5°C). Same root cause as EVT1, did we miss something?\n"
        "• 1 unit with cracked screen (drop from desk, 0.8m). Out of spec, "
        "but interesting — clip geometry held, fault is in the screen "
        "adhesive."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "Lin — pulling that unit. Cold-start brown-out feels like a "
        "soft-start timing thing on the buck, not the load issue we hit "
        "at EVT. May be a different root cause. Will scope this week."
    )),
    SeedMessage("#mech-design", *SARAH, text=(
        "On the cracked-screen-from-desk-drop: agreed clip retention is "
        "fine. The screen adhesive is a real concern though — we spec'd "
        "for 1.0m drop, but a 0.8m bag drop is below that and we're "
        "seeing damage. Looking at switching to a tougher OCA for V2."
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "Found and fixed the 3 silent units — customer-side WiFi MAC "
        "filtering. Sent them a setup guide. All 50/50 reporting now. "
        "Connection retry logic for V2: making the auth-fail backoff "
        "exponential instead of fixed."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "Cold-start issue: scoped it. Buck soft-start ramp is colliding "
        "with the SoC's POR window when ambient is below 8°C. Spec is "
        "0-40°C. This is a real bug. Two options:\n"
        "• HW: change RC on the buck enable pin (ECO, 3 weeks)\n"
        "• FW: software delay on POR before sampling the rail (1 day)\n"
        "Recommend FW patch for installed base, HW fix in V2."
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "Dan — FW patch is straightforward. PR up tonight, 200ms POR delay. "
        "Will ship in 1.0.1. Field push via OTA. Want me to ship to all 50 "
        "beta units or just the affected one?"
    )),
    SeedMessage("#general", *RAJ, text=(
        "Decision: ship 1.0.1 to all 50 beta units via OTA, no need to "
        "wait. Cold-start brown-out is a latent defect — fix proactively. "
        "Dan to file ECO for V2 hardware. Customer-facing comms: \"reliability "
        "improvement\" — no need to alarm them with \"brown out\"."
    )),
    SeedMessage("#compliance", *TOM, text=(
        "FCC ID grant received. CE Declaration of Conformity filed and "
        "acknowledged. Pre-MP marketing assets can now use both marks. "
        "Customs paperwork for EU shipments cleared."
    )),

    # ====================================================================
    # PHASE: Orion (parallel project — battery pack, EVT phase)
    # Different team members for this project
    # ====================================================================
    SeedMessage("#general", *NORA, text=(
        "Project Orion (battery pack) kickoff. Goal: 100Wh pack with "
        "smart BMS for the V2 platform. 8-week EVT timeline. Team: Elena "
        "(mech), James (elec), Dan supporting on EE bring-up, Lin on "
        "qual. Kickoff doc in /drive/Orion/."
    )),
    SeedMessage("#electrical", *JAMES, text=(
        "Orion EE schematics ready for review. Going with the same BMS "
        "IC family Atlas used (familiar driver stack saves us a month). "
        "Pack topology is 4S2P, 18650 cells. Voltage range 12.0-16.8V. "
        "Posting PDF in /drive/Orion/electrical/."
    )),
    SeedMessage("#mech-design", *ELENA, text=(
        "First Orion enclosure CAD up for review. Aluminum case, internal "
        "kapton wrap for cell isolation, M3 mounting on 4 corners. "
        "Pressure vent on the long edge per UL 2054. James — confirm vent "
        "doesn't conflict with your strain-relief routing?"
    )),
    SeedMessage("#electrical", *JAMES, text=(
        "Elena — vent location clear of my strain reliefs. One ask: can we "
        "move the BMS-to-pack connector 5mm inboard? Currently it's "
        "fouling the mounting boss. Sending an annotated screenshot."
    )),
    SeedMessage("#supply-chain", *MEI, text=(
        "Cell sourcing for Orion: lead-time on the Murata 18650 NCA is 14 "
        "weeks (!) post the China new year. Looking at Samsung INR18650-35E "
        "as alt — slightly lower energy density (3.5Ah vs 3.6Ah) but "
        "available in 4 weeks. Pack design needs to absorb the 100mAh "
        "delta. Elena/James — impact?"
    )),
    SeedMessage("#mech-design", *ELENA, text=(
        "Mei — Samsung INR18650-35E is the same form factor as Murata, "
        "no mech change. Good with the swap from my side."
    )),
    SeedMessage("#electrical", *JAMES, text=(
        "Confirming the Samsung swap is fine. We have ~3% margin on the "
        "energy spec, the 100mAh delta only eats 2.8% of it. Going with "
        "Samsung."
    )),
    SeedMessage("#general", *NORA, text=(
        "Decision: Orion cell sourcing switched to Samsung INR18650-35E. "
        "Mei to issue PO Mon. Original Murata schedule recoverable on V2 "
        "if Samsung quality data looks clean at DVT."
    )),
    SeedMessage("#qa-testing", *KARTHIK, text=(
        "Orion test plan first draft uploaded — /drive/Orion/qa/test_plan_v1.pdf. "
        "Covers UL 2054, UN 38.3, IEC 62133. ~14 weeks of cert testing "
        "after DVT freeze. Cycle life chamber blocked starting week 12."
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "Pulled in as a consult on the Orion BMS firmware. We can reuse "
        "75% of the Atlas charge controller stack. New code is "
        "fuel-gauge calibration + the 4S balancing logic. Estimating 2 "
        "weeks dev + 1 week verification."
    )),
    SeedMessage("#electrical", *JAMES, text=(
        "Orion EVT boards back today, 6 units. Bring-up: all 6 power on "
        "and report cell voltages correctly. One unit's voltage sense ADC "
        "reads ~30mV high across all 4 cells — same offset. Likely a "
        "reference issue. Investigating."
    )),
    SeedMessage("#qa-testing", *KARTHIK, text=(
        "Orion thermal pre-screen: ran a 4C discharge at 25°C ambient. "
        "Peak cell temp 48°C, pack ambient delta 12°C. Well inside UL "
        "limits. Pack thermal model lines up with the spreadsheet within "
        "8%."
    )),
    SeedMessage("#electrical", *JAMES, text=(
        "ADC offset root-caused: wrong resistor on the divider for cell 4 "
        "sense — 10kΩ instead of 10.5kΩ. BOM error caught by hand. "
        "ECO-Orion-002 to fix at DVT. For EVT we'll software-comp it."
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "James — software comp for the cell 4 divider is in. PR up. Calibration "
        "value is baked into the per-pack EEPROM at production test. "
        "Documenting the field-resilience risk: if EEPROM ever gets wiped "
        "we lose the comp. Recommend hard-fixing at DVT."
    )),

    # ====================================================================
    # RECENT (today / yesterday) — for fresh dashboard content
    # ====================================================================
    SeedMessage("#general", *RAJ, text=(
        "Heads up — week 4 customer review on Atlas tomorrow at 2pm. "
        "Two themes from beta telemetry: 100% battery-life conformance, "
        "and 1.0.1 OTA reduced the cold-start return rate from 2% to 0%. "
        "Pulling slides together — anyone with field photos pls drop in "
        "#general."
    )),
    SeedMessage("#manufacturing", *ANNA, text=(
        "MP yield this week: 97.2% (488/502). Best week yet. Lid press "
        "tooling fully bedded in, no rework. Adhesive surface prep SOP "
        "change holding — zero delamination flags."
    )),
    SeedMessage("#qa-testing", *LIN, text=(
        "HTOL day 21 update on Atlas: 30/30 units still operational. No "
        "parametric drift on key specs. We're at 504 of 1000 hours — "
        "halfway through the burn-in. Will declare reliability sign-off "
        "at hour 1000 (Sep 12, on plan)."
    )),
    SeedMessage("#electrical", *DAN, text=(
        "Atlas V2 EE re-arch sketch up — main change is moving to the "
        "next-gen SoC family (50% lower idle current) and the cold-start "
        "fix from beta. Sharing tomorrow with Sarah and Priya for review."
    )),
    SeedMessage("#supply-chain", *MEI, text=(
        "Vendor risk dashboard refresh:\n"
        "• ExtruCo: back to normal capacity, no current issues\n"
        "• AlumWest: hitting on-time delivery 100% for 6 weeks running\n"
        "• Samsung (Orion cells): first lot landed yesterday, IQC passed\n"
        "• Murata: still 12wk lead, not on the critical path"
    )),
    SeedMessage("#compliance", *TOM, text=(
        "UL 2054 testing for Orion booked at week 13 (Sep 28-Oct 4). "
        "Pre-test internal screening passes at our lab. CE marking review "
        "for Atlas V2 to start when we have a frozen BOM — likely week 11."
    )),
    SeedMessage("#firmware", *PRIYA, text=(
        "Released Atlas 1.0.2 to beta channel last night. Adds the "
        "exponential WiFi backoff fix and a small power optimisation for "
        "the sensor wake path. Telemetry overnight looks normal. Will "
        "promote to MP units next week if no surprises."
    )),
    SeedMessage("#general", *RAJ, text=(
        "Q3 program checklist for tomorrow's exec review:\n"
        "✅ Atlas: MP ramping, 50 beta units in field, reliability on track\n"
        "✅ Atlas V2: scoping complete, EVT start mid-Sep\n"
        "🟡 Orion: EVT validated, DVT board layout in review\n"
        "🔴 Cert calendar: tight on Orion UL window — week 13 booked but "
        "no float\n"
        "Open risks tracked in /drive/Program/risks_q3.xlsx."
    )),
)


async def _ensure_channel(client: SlackClient, name: str) -> str:
    """Create the channel if missing, join the bot, return channel id."""
    existing = await client.list_all_channels()
    for ch in existing:
        if ch.name == name:
            cid = ch.id
            try:
                await cast(Any, client)._post("conversations.join", {"channel": cid})
            except SlackAPIError as exc:
                log.info("slack.seed.join_skip", channel=name, reason=exc.error)
            return cid

    try:
        resp = await cast(Any, client)._post(
            "conversations.create",
            {"name": name, "is_private": "false"},
        )
        cid = cast(str, resp["channel"]["id"])
        log.info("slack.seed.created", channel=name, id=cid)
        return cid
    except SlackAPIError as exc:
        log.error("slack.seed.create_failed", channel=name, error=exc.error)
        raise


async def post_seed(bot_token: str) -> None:
    client = SlackClient(bot_token=bot_token)
    try:
        log.info("slack.seed.ensuring_channels", channels=list(CHANNELS))
        for name in CHANNELS:
            try:
                await _ensure_channel(client, name)
            except SlackAPIError:
                continue

        for msg in SEED_CORPUS:
            try:
                await client.chat_post_message(
                    channel=msg.channel,
                    text=msg.text,
                    username=msg.author,
                    icon_url=msg.icon_url,
                )
                log.info(
                    "slack.seed.posted",
                    channel=msg.channel,
                    author=msg.author,
                )
            except SlackAPIError as exc:
                log.error(
                    "slack.seed.failed",
                    channel=msg.channel,
                    author=msg.author,
                    error=exc.error,
                )
            await asyncio.sleep(POST_DELAY_SECONDS)
    finally:
        await client.aclose()


def main() -> int:
    token = os.environ.get("SLACK_DEMO_BOT_TOKEN")
    if not token:
        sys.stderr.write("SLACK_DEMO_BOT_TOKEN not set\n")
        return 2
    asyncio.run(post_seed(token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
