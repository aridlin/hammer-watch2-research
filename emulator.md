# Debug emulator and offline compiler lab

Updated 2026-10-29. Physical-watch testing remains deferred to the final version. All ADB commands in this repository address **emulator-5580 on server port 5038**. No host Bluetooth controller is bridged into the emulator.

## Initial baseline (historical; latest successful pairing/acquisition below)

- Android 15 / API 35 Google APIs x86_64 image, revision 9, with KVM. Its `libndk_translation.so` supports the acquired arm64 HAMMER App.
- All 20 verified HAMMER App 1.0.15 split APKs installed successfully. The original app code was not modified. First-run setup reached the main screen and device search without an account.
- The initial credential-free configuration POST returned application **401**. After direct user sign-in, the reconstructed authenticated POST returned **200** and six permitted Bluetooth names, including `HW2`. The target face catalog has not been downloaded.
- A Bumble 0.0.236 peer named `HW2` was discovered and connected on **local Android Netsim**. The app sent the initialization request twice, five seconds apart. It records writes and sends no protocol replies; application pairing remains incomplete.
- Blutter at commit `4a60ac648bf448c5a7596437243bcd0b9376fdf0` analyzed the app's ARM64 AOT library: Dart 3.9.2, snapshot `97ff04a728735e6b6b098bdf983faaba`. Recovered annotated assembly/object pools stay private; a method/address index is published.
- A separate SDK 10.7 harness compiled two reference faces **offline**. Its merged APK has no INTERNET or BLUETOOTH permissions. Its Java code never calls `initSDK`, upload, pairing or authentication.

The visible emulator and a persistent desktop reminder were opened at the user's request. The official app was navigated toward login so the user can enter credentials directly. App interaction and captures stopped during entry, then resumed after the user confirmed completion. Authentication succeeded. Credentials are not requested through chat or a custom credential form.

Evidence: [session summary](reports/emulator-session.json), [compiler results](reports/sdk-compiler-results.json), [AOT method index](reports/aot-method-index.json), [tool/source hashes](reports/emulator-source-manifest.json).

## Start, install and stop

The installed SDK was found at `/home/aridlin/.local/share/android-sdk`. The SDK location is configuration, not a requirement to install another global SDK. Use the appropriate SDK path on another machine.

```sh
export ANDROID_SDK_ROOT=/path/to/android-sdk
./tools/emulator-start --window > private/emulator/console.log 2>&1
```

Run that in a dedicated terminal. Omit `--window` for headless operation. The script creates only the project-local AVD and requires the existing `system-images;android-35;google_apis;x86_64` package. It does not download system images or alter an existing AVD. This workspace needed host execution for KVM access; KVM was unavailable inside the restricted filesystem view but verified usable on the host.

From another terminal:

```sh
./tools/adb-debug install-multiple -r private/apks/hammer-app/*.apk
./tools/adb-debug shell am start -n com.hammerup.app/com.creek.app.MainActivity
# Stop only this emulator, preserving its data:
./tools/adb-debug emu kill
```

Do not clear data or reinstall while the user is signing in. Do not automatically capture screenshots, UI XML, app data or logs during credential entry. Emulator disk images, generated ADB keys, app databases and logs remain ignored under `private/`.

## Build the offline oracle

`lab/android` is a small Java host of the vendor's published Creek SDK 10.7. It uses the **JX_3085C_PLATFORM** argument and 466×466 reference packs; this is not a declaration of HAMMER firmware compatibility. AndroidX Core is constrained to 1.15.0 so the lab builds against the available API 35. The chosen Dart compiler path worked; the x86 SDK logs a missing optional `libcreekActRes.so`, so other native-backed platform modes remain untested.

Build requirements: JDK 21, Gradle 8.10.2, Android platform 35/build tools, and network access to the SDK's Maven repositories. The lab does not include vendor binaries in Git.

```sh
keytool -genkeypair -keystore private/emulator/lab-debug.keystore \
  -storepass android -alias androiddebugkey -keypass android \
  -keyalg RSA -keysize 2048 -validity 3650 -dname 'CN=Local Offline Compiler Lab'
ANDROID_HOME="$ANDROID_SDK_ROOT" \
ANDROID_USER_HOME="$PWD/private/android-user" \
GRADLE_USER_HOME="$PWD/private/gradle-cache" \
gradle -p lab/android --no-daemon assembleDebug
```

The public debug key password is for a local test APK only. Use an existing compatible Gradle executable if it is not on PATH. The build emits `lab/android/app/build/outputs/apk/debug/app-debug.apk`.

After a userdebug emulator is running and no one is interacting with it:

```sh
./tools/adb-debug root
python -m tools.hammer_re extract \
  private/sources/CreekSDK/Example/CreekSDK/circlePhoto.zip \
  --destination faces/local/compiler-source
.venv/bin/python -m tools.sdk_compile_reference \
  --source faces/local/compiler-source/circlePhoto \
  --destination faces/local/circlePhoto.sdk10.7.bin
```

The helper checks emulator identity and debug build type, verifies the harness package and absence of network/Bluetooth permissions, rejects non-reference platform declarations, pushes only into the harness's own directory, runs compilation and validates the returned container CRC. It replaces only the harness's previous input/output, preserving host source packs. It refuses to overwrite the host destination. Do not run it while the user is entering credentials in the other app.

Observed outputs:

| Reference | Bytes | Resource entries |
|---|---:|---:|
| circlePhoto / photo | 39,398 | 58 |
| CW06G_TITAD101_01 | 251,663 | 95 |

Repeated compilation of circlePhoto produced identical bytes. Both binaries have exact JSON-IR reconstruction tests. All **147 BGRA image resources** decoded pixel-for-pixel to their original PNGs; two additional RGB565 resources also decoded. These results prove the observed container/image codec, not device installation or live sensor behavior.

## Virtual radio prototype

```sh
.venv/bin/python -m tools.watch_emulator \
  --duration 300 --log private/emulator/watch-events.jsonl
```

Only `android-netsim` and explicit localhost Netsim ports are accepted. USB/HCI/remote transports are rejected. Selected service/characteristic identifiers are experimental inferences from the app's matching code. There are no pairing, device-info, face-list, transfer or sensor replies yet; the app now recognizes the default `HW2` name and connects to the peer. A real implementation must respond to observed commands and use verified model metadata rather than fabricate a HAMMER firmware ID.

## Next runtime work

With sign-in complete, inspect the official app's own model/catalog flow using the disposable emulator. Keep tokens and account data private. Recover the actual model/firmware compatibility parameters before downloading target faces. Physical installation and live compass/altitude/pressure checks stay deferred. Later connection of the user's real watch is a separate, explicitly limited acquisition step.

References: [Android emulator CLI](https://developer.android.com/studio/run/emulator-commandline), [Bumble Netsim transport](https://google.github.io/bumble/transports/android_emulator.html), [Blutter](https://github.com/worawit/blutter).

## Authenticated client and observed initialization

```sh
chmod 600 private/auth/session.json
.venv/bin/python -m tools.catalog_client bluetooth-names \
  --session private/auth/session.json --destination private/auth/new-response.json
.venv/bin/python -m tools.creek_frame \
  private/emulator/watch-hw2-corrected-events.jsonl --events
```

The session file contains the observed `base_url`, raw `authorization` value and `app_info` map. The metadata is JSON-encoded in `App-Info`; the display app name is URI-encoded (`Hammer%20App`). These values come from app code and the signed-in lab, not a password collector. The client exposes only Bluetooth-name configuration and face-list reads, refuses redirects, bounds responses and never prints bodies/server error text. Face lists require all five explicit compatibility fields; there is no model-ID enumeration.

The initial local extractor incorrectly let an ASCII byte following an Isar string enter its JWT regex match. Respecting the stored string length fixed the request; the failed requests returned “Illegal token”. No token modification or authentication bypass was used. The durable client takes an existing private session and does not scrape credentials.

Observed initialization bytes: `c128010100010b000000000000`. Header fields are described by the offline inspector. Its declared length is 11 although the write is 13 bytes: trailing bytes and length semantics remain unresolved. No reply was invented. AOT selection maps textual `0001` to write and `0002` to notification; this direction is validated by the local app connection, while exact physical-watch UUIDs remain unverified.

## Emulator-first continuation — 2026-10-31

The user asked to keep pursuing emulation. Physical access is **not required for the next step**. The earlier suggestion that hardware acquisition was immediately necessary was premature. We extended the local-only peer and tested synthetic responses with the unchanged app, without restoring or modifying authentication.

`CmdIdMapper._map` at `0x1f43674..0x1f43688` maps the first command to `device` (main 1 / sub 0, wire bytes 4–5 `00 01`). `creek_parsiong.dart` at `0x1f01b14..0x1f01b34` decodes its body as `DeviceModel`/`protocol_device_info`. The vendor source `deviceinfo.pb.swift` publishes the response schema. `CreekTransport.seedData` at `0x243989c` sets declared length to 11 plus serialized protobuf length and builds C1/C2/C3 fragments. `parsingData` takes the body from offset 11 through two bytes before the end. The meaning/integrity of those trailer bytes and physical transfer variants remain unverified.

The new `--synthetic-device-info` peer mode supplies model 2039 and version 2.0.12 from the screenshots, with explicitly synthetic defaults for other fields. It refuses physical/remote radio transports. Notifications are deferred from the write callback, bounded to the negotiated ATT MTU, and split experimentally with two-byte C2/C3 continuation prefixes. A 20-byte minimal probe avoids fragmentation entirely. Neither full nor minimal responses completed app pairing; the app still retries its initial request. No target dial framework value was invented.

A private Android-emulator HCI capture independently confirms **six incoming ATT notifications** and **two outgoing write commands** in the captured test snapshot. Thus the synthetic response reaches Android's Bluetooth transport; app-side response acceptance is still unresolved. A fresh synthetic address did not resolve it. [`hci_summary`](tools/hci_summary.py) exports opcode counts, size histograms and candidate headers while omitting addresses and payloads. [HCI summary](reports/virtual-hci-summary.json), [trial results](reports/virtual-responder-results.json).

The optional Frida Java callback observer is **experimental and did not attach successfully**: a minimal x64 script ran, but loading the Java observer repeatedly failed with TransportError. No Java callback counts are claimed. Its server and ADB forward were removed. Emulator HCI diagnostics were disabled after acquisition. All raw captures, debug logs, APK wrappers and source bundles remain private. The main app's code was not changed.

**97 tests pass**, including synthetic protobuf field encoding, response gating, fragmentation bounds/reconstruction, private observer-output filtering, HCI-summary redaction and a real virtual-radio capture check. These tests do not prove app pairing, cloud acquisition, a complete virtual watch, physical compatibility or live complications. The cloud session's earlier application 509 remains a separate blocker to authenticated downloads; do not re-login automatically and displace the user's phone session.

Next: resolve the response contract using app-side parser evidence, then emulate the subsequent documented requests. A valid official-app login will be needed when cloud acquisition is ready. Keep physical testing deferred; escalate to hardware acquisition only if evidence shows an emulator/offline source cannot supply a required factory resource.

## Response routing breakthrough — 2026-10-31

The Java observer now works: transfer its bundled source in 32768-character RPC
chunks before evaluating it. A single large `create_script` transfer failed;
this was not evidence of ARM64 translation incompatibility. `observer_ready`
and `OnCharacteristicChanged` event names/sizes were observed without payloads.

The app SDK's private file `app_flutter/creek/20261031_log.txt` distinguished
successful reassembly from callback routing. Sequence high-bit correction
advanced the official app to Pairing and caused subsequent setup commands.
`tools/watch_emulator.py --synthetic-setup` now implements a limited schema-based
setup oracle, including normal-only virtual binding. It cannot access physical
radios; all advertised capabilities are synthetic. Pairing completion and face
catalog access remain unvalidated. Later testing reached the login screen as
the previous cloud session was invalidated elsewhere; no automatic re-login was
performed. Credentials should be entered directly in the official emulator app.

## Official pairing, gallery and compiler verification — 2026-10-31

After renewed direct user login, one synthetic peer completed normal binding;
the official UI showed Pairing Successful. The user separately approved submitting
the existing profile. Optional notification/background/Health Connect setup was
declined or skipped. The official gallery loaded, ADVENTURER and Modular
Compact-Weather were downloaded and their source ZIPs and compiled BINs pulled
into ignored local storage. No physical device participated.

The offline SDK helper now accepts the observed case-sensitive `ats3089C` source
label in addition to its earlier `ats3085c` references. The unchanged harness's
JX_3085C argument reproduced ADVENTURER's official BIN exactly, then successfully
compiled the orange digital source. Non-layout resources remained byte-identical.
All rendering and actual watch acceptance limits are recorded in STATUS.md.

## Complete virtual upload trial — 2026-10-31

A new synthetic peer used the confirmed non-identifying values platform3/color72/
framework8. The user approved unchanged repeated onboarding. Correct face-count
and storage fields were necessary to pass the official app's storage guard.
Color72 displayed orange ADVENTURER; the official compiled BIN remained identical
to color65, supporting retention of the original multi-palette metadata.

The app initially omitted ATT MTU negotiation. `request_virtual_mtu.js`, guarded
by debug-emulator checks and fixed Netsim identity04, requested517. Complete D1
start writes then arrived. `virtual_transfer.js` emulated receiver callbacks at
the Android boundary for that same synthetic identity; no host Bluetooth bridge
was installed. A reentrancy guard avoids double-counting Android write overloads.
A full official SDK upload completed: 427,972 bytes / 2,378 data frames, with
matching rolling CRCs and end callback success. Netsim-captured data reconstructed
byte-identically. This is a virtual transport proof, not physical ACK validation.

Optional Frida tooling uses loopback27042 forwarded to27043; servers/forwards are
stopped after the trial. Observer modes `virtual-*` actively emulate callbacks or
MTU for a fixed synthetic address; they are not passive observers. Raw payloads
stay private. Build JS bundles using the locally pinned esbuild0.28.2,
frida-java-bridge7.0.13 and buffer6.0.3; transfer bundle source in32768-character
chunks as required by this host's Frida transport. Never target a real watch
address in these scripts.
