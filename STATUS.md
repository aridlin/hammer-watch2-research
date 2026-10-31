# Project status

Updated **2026-10-31**. The current requested face is **Sci-Fi Timer (orange)**.
The edit removes EXPLORE, BE PROACTIVE, COLLABORATE, INNOVATE and SPORT plus arrows,
localizes weekdays to Polish, and replaces the small corner analog clock with
native compass widgets copied from the acquired weather face. It compiles and
passes offline resource/model checks. Hardware responsiveness/stability is unknown.

The requested Android installer is built and signed, with this face included.
It uses the already recovered GATT protocol, has no Internet/vendor SDK dependency,
and requires explicit user selection/Apply. Two emulator runtime tests pass,
including complete transfer with active-entry verification. No physical watch or
phone is used; desktop live installation remains blocked after the prior reboot.
The watch remains unpaired from the PC. See [installer](mobile-installer.md).

Prior ADVENTURER findings remain below. Revision 8 and diagnostic controls are
not enabled for installation. A single reported reboot is not a proven resource
exhaustion diagnosis. The new Sci-Fi edit totals 1,459,304 decoded image bytes,
versus 1,338,856 for its original; these sums are not peak firmware RAM.

| Revision | Physical result |
|---|---|
| 1 (`ewr24digital`) | Installed; time overlaps fixed meter icons; compass catches up on minute changes |
| 2 (`ewr24dig02`) | Offline experiment, never installed |
| 3 (`ewr24dig03`) | Installed and active; user confirms seconds work but compass still freezes; meters removed |
| 4 (`ewr24dig04`) | Installed; user confirms compass still broken. Weather font/date and badge removal requested. |
| 5 (`ewr24dig05`) | Installed; weather font, curved orange date without badge, weather heading widgets; runtime result pending |
| 6 (`ewr24dig06`) | Installed and active; Polish weekdays; compass still broken per user; weekday too high |
| 7 (`ewrcompass_24d07@LC`) | Installed; rejected: skipped seconds, slow compass, one reported reboot |

Revision 4 restores the factory hour/minute/second pointer geometry, dims the
hour/minute/hub sprites, and changes the second sprite to a short outer marker.
It adds native day plus twelve-image month array, rendered as DD.MM in place of
heart rate. AOD keeps hour/minute hands and date without a seconds animation.
White factory hand sprites are dimmed; meter icons/gauges are removed. The user's
remaining “white texture” report has no new close-up, so complete removal is
not yet claimed. Compass widgets themselves are unchanged. Retaining pointers is
a redraw hypothesis, not a proven fix. The host upload never modifies firmware.

Offline checks: **173 passed**, including actual source/compiler image guards.
Real sample tests skip when proprietary local samples are absent. Final acceptance
requires checking date, time, rim position, absence of unwanted graphics, and
continuous compass rotation on the physical watch. Earlier sections below retain
the first-install evidence; they do not override these later failures.

## Actual watch evidence

The Bluetooth identity matches the user's About screenshot; addresses and serials
stay private. The watch itself reports:

| Property | Result |
|---|---|
| Device / firmware | 2039 / 2.0.12 (minor field omitted; proto default 0) |
| Display | 466×466, round-corner parameter 233 |
| SDK platform enum | 3 = `JX_3085S_PLATFORM` in the published SDK |
| Color code | 72 (orange catalog variant) |
| Dial framework | 8 |
| Original installed faces / maximum | 10 / 24 (before test uploads) |
| Reported face storage | 40 MiB total; 2,719,744 bytes cloud usage |
| Compression | 4 (published LZ4 designation) |
| Actual ATT MTU / reported transfer MTU | 247 / 244 |
| Factory ADVENTURER | `ewrcompass_0819@LC.bin`, version 5, allocated size 458,752 |

The SDK enum name does not override the published ATS3089C chip specification.
Standard DIS strings literally read `Manufacturer` and `leopard`; no firmware OS
is inferred from them. The active face at inquiry time was the known comparison
face, not ADVENTURER.

Device, dial and MTU responses passed CRC16/CCITT-FALSE verification (init FFFF,
trailer little endian). Only fixed recovered inquiry requests were sent, plus
standard Bluetooth operations. No binding/settings/delete command was sent during these inquiries. The later
user-approved test upload is documented below. [Physical evidence](reports/physical-compatibility.json).

## Source, compiler and candidate

The authenticated official app downloaded actual ADVENTURER and Modular
Compact-Weather ZIP/BIN pairs in the emulator. Source ADVENTURER says `ats3089C`,
466×466, source frame 1, dial version 5. The original contains 128 resources.
The isolated SDK reproduces its official BIN byte-for-byte, including when compiled
with the real platform enum 3 and ARM64 ABI. Its APK has no network/Bluetooth
permissions and never calls upload/binding.

The preferred test artifact is **`faces/local/adventurer/ewr24digital.bin`**:

- 429,383 bytes; SHA-256
  `86e5600fd53f8204610f0ef8866b0eb7e1cf17d455b1ec2b33c38177a7417e61`.
- New name in both container and JSON, so the transfer targets a separate entry.
- Analog hour/minute/second hands and hub replaced with a 40-pixel `text/time`
  widget in normal/AOD layouts; calibration hint moved above the time.
- All 127 non-layout resources retain original hashes.
- Original palette metadata retained. Official color65/color72 BINs are identical;
  the device color selects the intended variant. Earlier forced-orange candidates
  remain diagnostic artifacts and are no longer the preferred installation input.
- Existing analog preview assets remain stale; no candidate rendering is claimed.

The time widget is present in a second real downloaded face. The candidate uses
the watch's 24-hour setting; actual midnight/leading-zero/AOD behavior remains to
be tested on hardware. Source compass, altitude, pressure, heart, steps, calories,
walking and UV bindings are retained. Explicit weather-condition and battery
widgets are absent from original ADVENTURER and have not been invented.

## Transfer implementation and validation

The official SDK completed a full upload of the original to the virtual lab:
D1 start, 2,378 D2 data packets, D4 end; its callback reported success. Captured
Netsim writes reconstruct byte-identically to the 427,972-byte original and pass
the transfer CRC16/XMODEM. ACKs were simulated at the emulator's Android callback
boundary, not received from physical hardware. The first emulator MTU failure and
a duplicate-hook counting error were corrected. [Transfer evidence](reports/virtual-transfer-validation.json).

`tools/watch_face_install.py` defaults to offline preparation. Physical execution
requires `--execute`, the exact reviewed hash, a private target and new log path.
It re-reads device/dial/MTU metadata, refuses an existing test entry, validates
space and target identity/capabilities, checks MTU bounds, and stops on any
rejection, missing ACK or offset/CRC mismatch. It has no firmware, deletion or
application-binding operation. A separately selected reviewed-test continuation
mode verifies the receiver's nonzero offset and prefix CRC before sending any
more data; it does not send a new start packet. Repeated ACK deliveries are
ignored. No activation command was sent; firmware activated the completed test
face automatically.
[Prepared upload plan](reports/standalone-install-plan.json).

**136 tests pass**, including real inquiry CRCs, original/candidate compiler
comparisons, real virtual-stream reconstruction, codec round trips, complete simulated D-Bus sender flows, actual physical ACK
validation, preflight refusal cases and preservation checks. Proprietary artifacts and raw account,
Bluetooth and notification logs remain ignored/private.

## Physical upload completed after explicit approval

The user approved adding the separate test face. Initial execution stopped after
180 bytes because a repeated start ACK reached the data waiter. A read-only D3
query independently confirmed offset180 and the candidate-prefix CRC. A second
continuation attempt sent only that query; its handler mistakenly excluded D3
replies and was corrected. Full simulated D-Bus tests now cover this case and
duplicate deliveries.

The completed continuation sent no new D1: it verified offset180 again, sent the
remaining data with matching offsets/rolling CRCs, and received a successful D4
end ACK. **429,383 bytes accepted; 2,387 accepted ACKs in the completed session**,
with 2,386 duplicate deliveries ignored. This establishes real transfer behavior
and verified continuation for this candidate, not every protocol variant.

A subsequent checksum-valid dial inquiry confirms:

- `ewr24digital.bin` is present and active.
- Original `ewrcompass_0819@LC.bin` remains present.
- Face count is now 11; the prior unrelated active face was not deleted.

[Physical installation evidence](reports/physical-installation-validation.json),
[post-install list summary](reports/physical-dial-after-install.json).

**Still pending:** user observation of actual HH:MM rendering, 24-hour correctness,
layout/orange palette, compass motion, altitude/pressure values and AOD. A stored
and active face is not proof of those visual/dynamic functions. Feedback has been
requested. No firmware flashing, bootloader change or cryptographic bypass occurred.
Do not rerun the uploader automatically after successful completion.

## Repository

Use `tools/git-project` for metadata in ignored `private/git` because this workspace
reserves read-only `.git`. Public snapshot: https://github.com/aridlin/hammer-watch2-research. See [README](README.md),
[protocol](protocol.md), [research](research.md), [format](format.md) and
[emulator lab](emulator.md).

## Revision 5 experiment

Actual time glyphs come from the acquired weather face unchanged (48×58 digits,
20×58 colon). Its weekday/day glyphs are colored orange. Weekday images bend along
the lower inner edge; day uses the existing curved renderer with the native day
binding. That combination is newly tested and its runtime behavior is unverified.
The heart badge is removed using a bounded row-gradient reconstruction.

The weather face's observed `icon/compass_icon` and `text/angle` bindings are added
alongside the original outer compass widgets. This tests whether the native
heading renderer activates sensor updates. There is no verified face-level
refresh interval; no undocumented device setting is sent. A moving heading with a
frozen outer ring would isolate the defect to the custom compass renderer.

Revision 6 localizes the Monday-first weather weekday array to `pon`, `wt`, `śr`,
`czw`, `pt`, `sob`, `ndz`. Source weekday indices 0..6 were visually verified as
MON..SUN. Numeric time/day glyphs remain from the weather face. Its English
weekday bitmap alphabet lacks some Polish letters, so only weekday labels use
local DejaVu Sans Bold Oblique; install that font to rebuild this revision.

The revision 6 dial list spans three ATT notifications; each fragment was delivered
twice through the observed host path. The inquiry parser now keeps raw and
adjacent-duplicate-suppressed interpretations and accepts only a CRC-valid message.
A fresh read confirms 15 installed faces, revision 6 active, and factory ADVENTURER
present. The initial unassembled reply was not evidence of missing/deleted faces.

## Revision 7: subtle clock reduction and integrated lower date

The user confirms revision 6 compass is still broken. `sob` is too high and feels
stickered on. Revision 7 lowers the weekday baseline radius from 130 to 138 pixels,
matching the numeric date renderer's radius. Clock glyphs change from 48×58 to
47×57; colon from 20×58 to 20×57. HH:MM:SS stays centered at x233, with overall
width 322 rather than 328 pixels (1.83% smaller).

Both acquired original compass face names contain `compass`; all prior test names
omitted it. A new separate `ewrcompass_24d07@LC.bin` preserves the factory naming
prefix/suffix while avoiding either factory filename. Filename-based firmware
sensor activation is an unverified hypothesis. Compass and pointer widget dicts
are identical to revision 6; no refresh-rate setting is invented. Cosmetics change
in the same iteration, so this is not a strict naming-only control. Physical
transfer and fresh metadata confirmation are recorded in reports/revision7-installation.json.

## Resource-budget audit after the reboot report

The full-screen weekday assets introduced in revision 5 were a significant design
mistake: 7 × 466 × 466 × 4 = 6,080,368 decoded pixel bytes. Original weather weekday
assets total 56,448 bytes. Original ADVENTURER image pixel sum is 3,177,836 bytes;
revision 7 image pixel sum is 9,349,444 bytes. These are sums of decoded assets,
**not measured peak firmware RAM**. Loading/caching and renderer scheduling remain
unknown, so an out-of-memory crash or watchdog has not been established.

Offline revision 8 crops weekdays to 61×33, moving their existing widget origin to
(181,338) so displayed pixels remain exactly identical. Weekday decoded pixel sum
becomes 56,364 bytes, a 99.07% reduction. This addresses demonstrable wasted image
storage; no claim of fixed seconds, compass or stability follows from it. Native
curved/day behavior and mixed compass renderer workload still require investigation.
No new face is sent to the watch. [Budget evidence](reports/decoded-image-budgets.json).

## Continued offline work; watch remains disconnected

The user authorized continued work without their watch. No Bluetooth discovery,
pairing, connection, inquiry or write is performed in this offline stage. Live
installation remains disabled. The isolated Android emulator compiler is the only
device-like target used; it is not a simulation of the watch firmware.

Three source controls were built with `tools.offline_experiments`, compiled and
validated against their base models:

| Control | Difference under study | Non-layout resources |
|---|---|---|
| Renamed factory | Only JSON/container name changes from original | All 127 preserved |
| Factory plus seconds | Adds one existing-font text/second widget; name differs | All 127 preserved |
| Cropped original compass | Removes only the two added weather heading widgets from revision 8; name differs | All 157 preserved |

All have valid container CRCs and exact expected model dictionaries. Original
assets remain local/private. These controls have no uploader integration and have
not been tested on hardware. A future comparison of the renamed clone with the
seconds-added clone can isolate the added text widget; cropped revision 8 versus
the third control compares the extra weather heading widgets. Different names
remain an unavoidable confound until firmware name handling is understood.

Offline static APK analysis also identified `DeviceUpgradeRequest.path`
(`0x2dd2048`), `DeviceUpgradeRequestModel.toJson` (`0x247178c`), firmware URL/version
response keys, and `FirmwareLogSyn.firmwareLog` (`0x2300a18`) calling SDK
`CreekDown.startLog` (`0x2300bf4`). These are leads for legitimate image acquisition
and diagnostics, not recovered firmware or crash evidence. No service was queried,
embedded authorization used or logging command sent. See
[controls](reports/offline-controls-validation.json) and
[diagnostic leads](reports/offline-diagnostic-leads.json).

## Sci-Fi Timer source and installer evidence

The official cached catalog identifies `CWR05G_23612`, version 5. Its archive
contains actual color variants under `app/color_picture`, including the requested
orange `#B87F44`. The candidate keeps source platform `ats3085s`, frame 1, dial
version 5 and dial type 6. Only layout JSON, seven 56×20 weekday images and the
orange background differ among the 102 original compiled resources; all other
93 original resources remain byte-identical. Twenty-four small compass assets
are copied from the weather face. Three pointers and their hub are replaced by
six native weather widgets, translated to center (341,135). No full-screen weekday
sprites or new curved-date bindings are introduced.

The final BIN is 143,415 bytes, 126 resources, valid CRC32. Both original/modified
sources compile under the already confirmed JX_3085S platform argument. The APK
is signed separately from the vendor app and embeds only a package public key and
the modified face package, not credentials or signing secrets. Source/cache signed
URL queries are omitted from all public reports.

The synthetic Android run receives exactly all 143,415 bytes in 797 data frames.
It confirms the new face entry active in synthetic metadata, and rejects a tampered
signed package. This proves the Android transport/package path only. It does not
validate firmware rendering, compass freshness, counters or stability. Release
lint has no issues and Google apksig verifies the APK. Local deliverables and
checksums are in dist/; public evidence is in reports/scifi-*.json and
reports/installer-*.json.
