# Bluetooth and watch-face transfer investigation

> Status note, 2026-10-31: sections record successive investigation stages.
> Physical uploads and digital seconds are now verified. Custom compass refresh
> remains broken; original factory compass works. See STATUS.md for current scope.


Current update (2026-10-31): normal virtual pairing succeeded, the official gallery
downloaded ADVENTURER source and compiled BIN, and response sequence/framing is
partially validated. Physical transfer and encrypted reconnect remain unverified.
The final sections supersede earlier initialization-only observations.

Status: **app-level header/selection code recovered; physical HAMMER wire behavior unverified.** Research date: 2026-10-29. A local Netsim peer named `HW2` achieved app discovery/GATT connection and received initialization writes; application pairing remains incomplete. No physical device or radio was accessed.

## Evidence layers

| Layer | What is known | Evidence / limitation |
|---|---|---|
| Resource provisioning | Creek supports source ZIP packs and precompiled BIN resources | Pinned developer guide `content/en-US/flutter/watch-faces.md`; exact HAMMER download request unresolved |
| SDK encoding | Parse source directory → choose options/functions → encode binary | Android `CustomDialScreenViewModel` and Swift `CreekSDKExtension`; separate offline reference harness executed |
| SDK transfer | `upload` / Android demo `uploadNew` takes filename and bytes, with progress, success and failure callbacks | SDK demo calls with `<face-name>.bin`; do not treat this as a raw BLE packet |
| Face management | Query available faces, select by name, delete by name | SDK API/protobuf model; not used on hardware |
| BLE framing | Header conversion code recovered; runtime validation pending | No physical capture or successful simulator handshake |
| Integrity/authentication | Unknown for face transfers | App package signatures are separate from resource integrity |

## Published face-management messages

Source: [Creek developer guide, pinned watch-faces page](https://github.com/creekwearable/CreekDeveloperGuide/blob/f6fd1e1fce415e1822f39a09299b0cd09f938cf7/content/en-US/flutter/watch-faces.md), cross-checked against `watchdial.pb.swift` in the source manifest.

| Message | Relevant protobuf field numbers |
|---|---|
| `protocol_watch_dial_plate_list_item` | 1: face category; 2: version; 3: byte size; 4: name bytes |
| `protocol_watch_dial_plate_operate` | 1: operation; 2: repeated face names; 3: repeated ordering names |
| `protocol_watch_dial_plate_inquire_reply` | 3: framework version; 4–9: cloud/photo/wallpaper counts; 10: face entries; 11–13: capacity/usage; 14: active face name; 15: compression capability; 16: function flags; 17–18: photo/total limits |

Published operation values are inquiry 0, selection 1 and deletion 2. Published face categories distinguish general, photo, wallpaper, custom and AOD variants. The inquiry model's compression field documents 0 for none and 4 for LZ4. Function-flag bit 0 describes face ordering. These values are **vendor SDK definitions**, not observed commands for this watch.

The schema uses protobuf integer fields. Comments such as “1bytes” or “4bytes” describe intended value bounds; they do not establish a fixed-width byte layout. The SDK sources contain newer fields beyond some documentation revisions; negotiate/query the device rather than assuming every field is supported.

Catalog compatibility requires the firmware/device ID to be included in the supported devices and the device's `plateVersion` to meet the resource's required framework version. Screen dimensions alone are insufficient. The same API surface also handles other file categories, including firmware: do not use a generic upload function with unverified file types.

## GATT observations and unknowns

The acquired `libapp.so` contains literal `00000FF0-0000-1000-8000-00805f9b34fb` and the standard CCCD identifier `00002902-0000-1000-8000-00805f9b34fb`. Exact offsets and library hash: [native findings](reports/android-native-findings.json).

AOT analysis now traces service matching to `CreekScanBind` at `0x2c3f964` and the normal manager around `0x242e0a0`, comparing the text `00000ff0`. Characteristic selection compares `0001` (write) and `0002` (notification); the complete physical UUIDs and physical properties have not been established. The virtual peer's UUIDs are hypotheses, not a discovery result. Keep `0FF0` distinct from CMF's `FFF0`. CCCD presence is generic.

`HeadModel.uint8ListToModel` at `0x1f42fd8` requires an 11-byte header. Its inverse is `modelToUint8List` at `0x243ad2c`. Recovered fields are: type byte at 0, sequence byte at 1, priority/flags at 2, a control field at 3, two command bytes at 4–5, little-endian length at 6–9 and code at 10. The type encoder selects C1/C2/C3 for start/middle/end and CC/CD for stop-request/stop-receive. This is a static interpretation of app code; no response generator or physical transport has been validated. MTU, fragmentation/reassembly, authentication, retries and finalization remain unresolved.

`com.example.creek_blue_manage.CreekBlueManagePlugin` was decompiled with JADX 1.5.6. The inspected wrapper implements phone permissions, calls and lifecycle bridging; its name alone does not establish that it contains the face transport. Flutter/AOT analysis or focused captures remain necessary.

## Installation routes

| Route | Present state | Next evidence required |
|---|---|---|
| Official HAMMER face gallery/photo flow | Advertised; preferred | Matching face resource and successful observed install |
| Local cached-file replacement | Unverified | Actual private cache path, integrity behavior and a reversible official flow |
| Existing third-party tools | No demonstrated HAMMER support | Exact format and protocol compatibility, not shared chipset |
| Documented Creek SDK transfer | Public API exists; HAMMER compatibility untested | Firmware/device ID, framework version and controlled official baseline |
| Custom companion app | Deferred | Verified transport and resource validation; no uploader implemented |

## Capture procedure, when needed

First identify the watch/app versions and face names. Then, on the user's own phone, capture only a short official face-list/download/install flow using Android's Bluetooth HCI snoop facility. Enabling that facility is a user action; this repository does not change phone settings. Avoid unrelated calls, messages and health sync during the capture. Keep the original log in `private/`, never in a public issue or commit.

Analyze service discovery and transfer traffic offline, separating phone network downloads from BLE writes. Use stable pseudonyms for device identities and redact keys, tokens, addresses and unrelated payloads. Document framing only when validated across multiple transfers, including failures/cancellation if available. No capture has been supplied or decoded, so no packet-level claims are made.

No firmware flashing, bootloader modification, signature bypass, factory shell or undocumented write command is authorized or implemented.

## Catalog runtime findings

The app's `DialListRequest.path` and `AllDialListRequest.path` now identify `/service-parts/v1/dial/pages` and `/service-parts/v1/dial/listFirmware`. `BaseRequest.httpMethod` resolves to **POST**. Compatibility request-model keys include `firmwareId`, `appFrameVersion`, `firmwareFrameVersion`, `customerCode` and `snCode`; the pages model also carries classification/pagination fields. The authenticated configuration header construction is verified; exact target compatibility values remain unresolved.

`BaseRequest.authority` selects `Global.serverNode`; the default release node is `https://cloud-frankfurt.creekcould.com`, also observed in the disposable app's startup log. The earlier `app.hammerphones.com` string occurs in a sharing URL and is **not evidence of the catalog's API host**. A credential-free POST to the recovered Bluetooth-configuration endpoint returned application code 401. No login bypass or model-ID enumeration was attempted.

The user signed in through the visible official app after requesting a login reminder. Automation paused during entry and resumed after confirmation; configuration requests now return application code 200. Physical-watch testing remains reserved for the final version. See [emulator.md](emulator.md).

## Virtual connection evidence (authenticated stage)

The configuration endpoint returns six app-supported names: `HW2_LITE`, `HW2`, `123`, `Hammer Ventus`, `Ventus Pro`, `HW3`. This is a Bluetooth-name allowlist, not a firmware-ID mapping. Changing the virtual name to `HW2` exposed it in the official app. After correcting the characteristic direction, the app subscribed and wrote `c128010100010b000000000000`, repeated about five seconds later. No response, application pairing or face transfer succeeded.

The complete experimental virtual UUIDs remain `00010000-0000-1000-8000-00805f9b34fb` (write) and `00020000-0000-1000-8000-00805f9b34fb` (notify). Their successful selection demonstrates the app's substring matching, not that these are the physical watch's exact UUIDs. An earlier reversed mapping caused a missing-CCCD error.

[`creek_frame`](tools/creek_frame.py) inspects only the 11-byte header, preserves both command bytes separately and omits payloads. The 13-byte observation has declared length 11 and two unclassified following bytes. Do not assume payload length, checksum coverage or a combined numeric command semantic from this observation alone. [`virtual-header-observations.json`](reports/virtual-header-observations.json) contains only nonpersonal header fields.

The request header `Authorization` contains the app's raw session token, and `App-Info` contains JSON metadata. `Networks.send` at `0x1fdf258` builds the latter. Token values, private database records and account IDs remain excluded from published evidence. The tested read-only client refuses redirects and requires verified compatibility inputs for face queries. Authentication is no longer a blocker; firmware ID, device dial framework, customer selection and factory resources are.

## User target confirmed — 2026-10-31

The user selected **ADVENTURER**, the default face shown in the first supplied app screenshot. The second screenshot identifies the device as **HW2**, model **2039**, firmware **V2.0.12**. Personal serial/MAC values are intentionally omitted; original screenshots remain ignored under `private/references`. The screenshot is an app/rendered reference, not a live sensor validation.

The Model No. view (`about_watch.view.dart` at `0x324ed80..0x324eda8`) reads controller field_2b. `AboutWatchController.getLocalDeviceInfo` at `0x29c24f8..0x29c2540` fills that with formatted `DeviceModel.field_7`. `FaceGalleryController._getDialMarketFromNet` at `0x2a62c7c..0x2a62d24` uses the same field for the request's firmwareId. This supports **2039** as the catalog firmware ID in the acquired build, rather than treating the regulatory model code alone as proof. Server confirmation remains pending.

A read-only model/color query for that ID returned application **509**, “Account logged in at another location.” The old session is invalidated; the response establishes nothing about this model's catalog or color. No automatic re-login was attempted. A share link from ADVENTURER's share button is the least disruptive next acquisition lead; whether it exposes a usable resource is unverified. Device dial framework (`plateVersion`) and actual face resources remain missing.

A further code check corrected the client schema: `snCode` is an **integer device code**, not the displayed serial-number string (`AllDialListRequestModel.toJson`, `0x227ed14..0x227ed3c`). The gallery uses a default value of 65 when its device field is absent; that fallback is not asserted to be this watch's actual value. Customer code derives from `DeviceSnModel.customerIdToASCLL`; it is also unverified. No personal serial was submitted to the API. See [target evidence](reports/target-adventurer.json).

## Emulator-first continuation — 2026-10-31

The user asked to keep pursuing emulation. Physical access is **not required for the next step**. The earlier suggestion that hardware acquisition was immediately necessary was premature. We extended the local-only peer and tested synthetic responses with the unchanged app, without restoring or modifying authentication.

`CmdIdMapper._map` at `0x1f43674..0x1f43688` maps the first command to `device` (main 1 / sub 0, wire bytes 4–5 `00 01`). `creek_parsiong.dart` at `0x1f01b14..0x1f01b34` decodes its body as `DeviceModel`/`protocol_device_info`. The vendor source `deviceinfo.pb.swift` publishes the response schema. `CreekTransport.seedData` at `0x243989c` sets declared length to 11 plus serialized protobuf length and builds C1/C2/C3 fragments. `parsingData` takes the body from offset 11 through two bytes before the end. The meaning/integrity of those trailer bytes and physical transfer variants remain unverified.

The new `--synthetic-device-info` peer mode supplies model 2039 and version 2.0.12 from the screenshots, with explicitly synthetic defaults for other fields. It refuses physical/remote radio transports. Notifications are deferred from the write callback, bounded to the negotiated ATT MTU, and split experimentally with two-byte C2/C3 continuation prefixes. A 20-byte minimal probe avoids fragmentation entirely. Neither full nor minimal responses completed app pairing; the app still retries its initial request. No target dial framework value was invented.

A private Android-emulator HCI capture independently confirms **six incoming ATT notifications** and **two outgoing write commands** in the captured test snapshot. Thus the synthetic response reaches Android's Bluetooth transport; app-side response acceptance is still unresolved. A fresh synthetic address did not resolve it. [`hci_summary`](tools/hci_summary.py) exports opcode counts, size histograms and candidate headers while omitting addresses and payloads. [HCI summary](reports/virtual-hci-summary.json), [trial results](reports/virtual-responder-results.json).

The optional Frida Java callback observer is **experimental and did not attach successfully**: a minimal x64 script ran, but loading the Java observer repeatedly failed with TransportError. No Java callback counts are claimed. Its server and ADB forward were removed. Emulator HCI diagnostics were disabled after acquisition. All raw captures, debug logs, APK wrappers and source bundles remain private. The main app's code was not changed.

**97 tests pass**, including synthetic protobuf field encoding, response gating, fragmentation bounds/reconstruction, private observer-output filtering, HCI-summary redaction and a real virtual-radio capture check. These tests do not prove app pairing, cloud acquisition, a complete virtual watch, physical compatibility or live complications. The cloud session's earlier application 509 remains a separate blocker to authenticated downloads; do not re-login automatically and displace the user's phone session.

Next: resolve the response contract using app-side parser evidence, then emulate the subsequent documented requests. A valid official-app login will be needed when cloud acquisition is ready. Keep physical testing deferred; escalate to hardware acquisition only if evidence shows an emulator/offline source cannot supply a required factory resource.

## Runtime response routing — 2026-10-31

The unchanged HAMMER App accepted synthetic DeviceModel data from the local
Netsim peer and advanced to **Pairing**. The missing condition was sequence bit
7: the request correlation is `sequence & 0x7f`, while replies must set
`sequence | 0x80`. `CreekGlobalNotice._doTask` at AOT `0x240a348`
(mask at `0x240a458`, dispatch at `0x240ad48`) sends values <=127 to unsolicited
UpdateNotice rather than the queued request callback. Runtime SDK diagnostics
confirmed reassembly and callback progression after setting the response bit.
This establishes an app contract in the virtual lab, not a physical-watch trace.

Accepted device replies use the 11-byte header, protobuf body and two zero
trailer bytes, split into C1/C2/C3 notifications at ATT MTU minus 3. The trailer's
integrity semantics remain unverified. Typed outgoing MTU, app-table, language,
time and user requests omit this trailer; empty device inquiries include it.
The responder uses an explicit command allowlist rather than assuming one
universal trailer rule.

Recovered setup main/sub commands are 1/0 device, 2/0 time, 3/0 user, 4/0
language, 5/0 binding, 21/0 sport, 22/0 watch dial, 30/0 function table, 30/1
app table, 34/0 MTU and 42/3 voice assistant. Sources: pinned SDK protobuf files
and `cmd_id_manager.dart` AOT `_map` at `0x1f4364c`. The virtual setup responder
supplies synthetic capabilities, not discovered physical values. Its dial
framework default 9 is explicitly a lab parameter; the real plateVersion is
still unknown. Normal bind method 1 / success flag 2 follow `binding.pb.swift`
and `enums.pb.swift`; encrypted binding is refused. Normal-bind completion is
not yet validated in the app.

The SDK reduces a reported transfer MTU <=180 by 10 (`creek_blue.dart`, AOT
`0x242baa4..0x242bab4`). The lab reports 30 so the resulting frame budget is 20
for ATT MTU 23. This adjustment still needs runtime validation. No physical
Bluetooth adapter or target watch was used.

## Successful virtual pairing and acquisition — 2026-10-31

Normal bind request main/sub 5/0 with protobuf method=1, flag=0 received a reply
method=1, flag=2. The official UI displayed Pairing Successful. Dial inquiry 22/0
was observed as the 13-byte typed request `c13c010100160d000000000800`: its body
is `operate=0` (inquire), with no trailer. The responder was corrected accordingly.
The isolated peer now has a process lock to prevent duplicate synthetic identities.

On interrupted/restarted connections the app also requests method=0 encrypted
binding. The responder refuses this form; first-time pairing success does not
prove reconnect authentication. No keys/challenges are fabricated or bypassed.

The official app downloaded source ZIPs under
`app_flutter/dial/<virtual-peer-id>/<face-name>.zip`, extracted `firmware/dial.json`
and assets, then wrote `<face-name>.bin`. ADVENTURER's actual generated BIN and
a second catalog BIN validate the existing index/CRC parser. Add/Update calls
`DialRegularController.onUpdatePressed` (`0x336ad94`), which passes
`forceDownload=true` to `_prepareRegularDial` (`0x336b2c8`) before local encoding
(`encodeDial`, `0x336af9c`). A persistent local-cache replacement path is therefore
not established. Neither custom transfer nor transfer finalization has been tested.

## First physical connection — 2026-10-31

User-authorized system pairing succeeded after the phone's Bluetooth was switched
off. The identity matches the user-supplied About screenshot, retained privately.
A later standard connection completed GATT discovery, independently verified by
BlueZ: Connected/Paired/Bonded/ServicesResolved all true.

| Actual physical GATT service | Characteristic | Observed properties |
|---|---|---|
| `00000ff0-0000-1000-8000-00805f9b34fb` | `00000001-0000-1000-8000-00805f9b34fb` | write, write-without-response |
| same | `00000002-0000-1000-8000-00805f9b34fb` | notify |

This confirms the short service and directions, while correcting the earlier
hypothetical full virtual characteristic UUIDs (`00010000` / `00020000`). Also
observed standard GAP, GATT, Device Information, Battery and vendor `ffd0`
services. No proprietary requests or notification subscriptions were sent.
Standard DIS strings are literally `Manufacturer` and `leopard`; no OS/platform
conclusion follows from them. Standard PnP/battery reads remain private. Actual
protocol device info, dial inquiry, application binding and transfer are pending.
[Redacted physical evidence](reports/physical-pairing-progress.json).

## Physical read-only protocol confirmation — 2026-10-31

The fixed device inquiry (1/0), dial inquiry (22/0, operate=0) and MTU inquiry
(34/0, operate=1) all returned successful matched replies. Their trailers validate
as CRC16/CCITT-FALSE over the complete reassembled message before the trailer,
init FFFF, little-endian trailer. This differs from the file stream checksum below.
Three real reply captures validate the implementation. MACs, serials, account
fields and personal face names are excluded from published summaries.

Actual platform enum is 3 (`JX_3085S_PLATFORM`), color 72, framework 8, ATT MTU247,
reported transfer MTU244. BLE PRN is absent/default0 in the received schema;
no physical file-transfer acknowledgment behavior is claimed yet.

Correction to the earlier MTU interpretation: the inspected branch retains the
SDK's default for small reported MTUs; it subtracts 10 when the report exceeds
180 (with a separate larger-MTU clamp). Reporting 30 did not yield 20-byte SDK
frames: observed SDK data packets still carried 180 bytes. Explicit emulator
ATT negotiation to 517 fixed truncation. No physical MTU setting was changed.

## Observed virtual upload variant — 2026-10-31

Pinned AOT evidence: `CreekUploadHead.modelToUint8List` 0x21564e8,
`CreekReplyModel.uint8ListToModel` 0x23f47b8,
`CreekUpload.startUpFile` 0x23f4a60, `middleUpFile` 0x23f5458,
`endUpFile` 0x23f7a1c, and
`BlueTool.getCRC` 0x23f4654. Numeric enum mapping plus actual official-app writes
confirm D1=start, D2=middle, D3=queryIndex, D4=end. Other variants remain untested.

| Frame | Observed representation |
|---|---|
| D1 start | `D1 00`, LE32 transfer size, LE32 original size, parameter byte `01`, NUL-terminated filename |
| D2 data | `D2 00`, raw contiguous binary bytes; tested SDK chunk size 180 |
| D4 end | `D4 00 00`, LE32 field carrying the file's CRC16/XMODEM (init0) |
| Simulated ACK | same opcode, second header byte, status0, optional LE32 accepted offset and LE32 rolling CRC16/XMODEM; data ACKs used all 11 bytes |

The 427,972-byte official ADVENTURER stream completed with 2,378 data frames and
end CRC 42872 (A778). SDK diagnostics reported upload success. Independent
reconstruction from Netsim writes matched the original SHA-256 exactly. ACKs
were injected only for fixed Netsim address identity04 inside the debug app;
original GATT writes proceeded to Netsim. This proves app/codec behavior for the
observed variant, not physical firmware acceptance or resume/auth semantics.

The physical uploader is explicitly gated, targets only separately named
`ewr24digital.bin`, verifies fresh compatibility, and stops on unexpected ACKs.
It does not send a resume, binding, set-face, delete, firmware or cancel command.
Only user-approved physical testing can establish real file-transfer behavior.

## Actual test-face upload and verified continuation — 2026-10-31

After explicit user approval, `ewr24digital.bin` was uploaded as a separate name.
No factory face delete/overwrite or firmware operation occurred. Physical ACKs
confirm D1 status success in3 bytes; D2 status/offset/rolling CRC in11 bytes;
D3 receiving offset/rolling CRC in11 bytes; D4 end status in3 bytes.

The first attempt stopped at180 bytes because a repeated D1 ACK was treated as
an unexpected data response. The live D3 query (`D3 00`, recovered from SDK
`queryPosition` 0x23f3d84) returned offset180 and the matching reviewed-candidate
prefix CRC. Duplicate notification deliveries must be ignored or routed by opcode,
as the SDK does. The origin of duplication (wire versus host delivery) has not
been established by a physical HCI capture.

A separately selected reviewed-test continuation verifies nonzero offset/alignment
and candidate-prefix checksum, then continues D2 without resending D1. The first
continuation's D3 filter omission was corrected and covered by an end-to-end fake
D-Bus test. The completed physical session accepted2,385 remaining D2 packets,
with all offsets and CRCs matching, then accepted D4. Its accepted ACK count is
2,387 including D3 and D4;2,386 duplicate deliveries were ignored.

The final CRC-valid dial response lists both the original and new test, and names
the new test as active. The firmware activated it after upload; no explicit
set-face command was sent. BLE PRN was absent/default0, and stop-and-wait transfer
worked in this actual case. Other chunk sizes, transport variants, errors and
resumptions are not claimed tested. [Physical result](reports/physical-installation-validation.json).

BlueZ later reported ServicesResolved=false despite working standard GATT reads.
Known characteristic paths plus fresh CRC-valid device/dial/MTU inquiries proved
the link remained usable. The tool still requires a paired/connected exact private
target, discovered Creek characteristics and matching live inquiry metadata;
it no longer treats this advisory flag alone as a reason to reject an operational
link. This change was verified with real replies before any upload data was sent.

## Later physical face iterations

Revision 3 transferred 416,683 bytes as `ewr24dig03.bin`, was reported active by
fresh dial metadata, and retained factory ADVENTURER. User reports working digital
seconds but frozen compass. Revision 4 uses a new `ewr24dig04.bin` entry and the
same validated D1/D2/D4 transfer. No activation opcode, delete, factory overwrite,
firmware command or retry on an unknown offset is added. Transfer acknowledgment
and runtime face correctness are separate acceptance criteria.

## Duplicated inquiry fragments with a longer face list

After revision 6, dial metadata totals 481 bytes and spans C1/C2/C3 notifications.
The observed host delivered each fragment twice. The former assembler appended
the second C2 twice and exceeded the declared length. `CheckedInquiryAssembler`
now keeps raw and adjacent-duplicate-suppressed interpretations, bounds each via
the existing assembler, and accepts only a CRC16-valid complete response. Keeping
the raw interpretation avoids assuming identical continuation bytes are always
duplicates. A synthetic doubled-fragment test and actual captured response pass.
A fresh CRC-valid inquiry confirms revision 6 active and factory retained.

## Live testing suspended after stability report

The user reports irregular seconds, slow compass and one reboot on revision 7.
All live uploader entry points are now blocked before device or target access;
there is no command-line override. Transport ACK/reassembly validation remains
valid evidence of received bytes, not face runtime safety. The isolated sender
unit tests explicitly disable this guard only inside their simulated D-Bus scope.
Offline resource budgeting identifies excessive full-screen weekday canvases;
revision 8 is compiled offline only and is not enabled in the installer.

## Static diagnostic leads while disconnected

The official app exposes a firmware upgrade request at
`/service-device/v1/upgrade` through `DeviceUpgradeRequest.path`, and firmware URL
fields in its response model. This is not a new executed API client. Likewise,
`FirmwareLogSyn.firmwareLog` reaches `CreekDown.startLog`, but its transport command
and payload are not approved for use, implemented or sent here. No crash-log
availability is claimed. See reports/offline-diagnostic-leads.json for code
addresses and hashes. The public repository excludes embedded authorization.

## Native Android installer, reusing the recovered protocol

`lab/android/installer` implements the same service and characteristic UUIDs,
fixed device/dial/MTU inquiries, CRC16/CCITT-FALSE metadata verification, and
D1/D2/D4 transfer used by the PC prototype. Android first negotiates MTU and enables
the notification CCCD. Fresh target profile/capacity checks precede file writes;
existing destination filenames are refused. File chunks are at most 180 bytes.
No new binding/activation/delete/firmware command has been reverse-engineered or
introduced. The phone user must explicitly connect and Apply.

The asynchronous Android state machine waits for custom receiver ACKs and avoids
sending another GATT request while Android reports a write in flight. It ignores
any older DATA ACK only if that offset/CRC was previously committed, so a delayed
duplicate cannot abort a later block or advance the stream. Unrelated notifications
are filtered before feeding the requested fragmented metadata assembly. File
transfer failures stop without retry/resume. D4 acceptance is recorded separately
from subsequent list/active verification, so final verification failure does not
falsely imply the file was never accepted.

Emulator testing uses an exact-fixture receiver confined to Android Netsim. Its
response fragments cap attribute values at 512 even if negotiated MTU is 517;
the previous synthetic 514-byte notification was not delivered by Android. This
was a simulator defect, not evidence of a new HAMMER command. The receiver
validates every data byte and rolling CRC against the selected local fixture.
The instrumentation APK refuses non-emulator targets and is separate from the
release installer. [Runtime proof](reports/installer-emulator-validation.json).
