# Project status

Updated **2026-10-31**. Physical installation works, including separately named
faces and digital seconds. The factory ADVENTURER remains intact. The requested
custom face is **not accepted as complete**: compass refresh is still broken.

| Revision | Physical result |
|---|---|
| 1 (`ewr24digital`) | Installed; time overlaps fixed meter icons; compass catches up on minute changes |
| 2 (`ewr24dig02`) | Offline experiment, never installed |
| 3 (`ewr24dig03`) | Installed and active; user confirms seconds work but compass still freezes; meters removed |
| 4 (`ewr24dig04`) | Installed and active; factory retained; runtime feedback pending (reports/revision4-installation.json) |

Revision 4 restores the factory hour/minute/second pointer geometry, dims the
hour/minute/hub sprites, and changes the second sprite to a short outer marker.
It adds native day plus twelve-image month array, rendered as DD.MM in place of
heart rate. AOD keeps hour/minute hands and date without a seconds animation.
White factory hand sprites are dimmed; meter icons/gauges are removed. The user's
remaining “white texture” report has no new close-up, so complete removal is
not yet claimed. Compass widgets themselves are unchanged. Retaining pointers is
a redraw hypothesis, not a proven fix. The host upload never modifies firmware.

Offline checks: **146 passed**, including actual source/compiler image guards.
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
reserves read-only `.git`. No remote/publication exists. See [README](README.md),
[protocol](protocol.md), [research](research.md), [format](format.md) and
[emulator lab](emulator.md).
