# Research and verified observations

> Status note, 2026-10-31: sections record successive investigation stages.
> Physical uploads and digital seconds are now verified. Custom compass refresh
> remains broken; original factory compass works. See STATUS.md for current scope.


Research date: **2026-10-29**. “Confirmed” below describes the cited publication or inspected artifact, not an unperformed physical verification. APK observations apply to the acquired mirror version, not necessarily the version on the user's phone.

## Hardware and identity

| ID | Finding | Evidence | Confidence / limits |
|---|---|---|---|
| H1 | Published chipset is **Actions ATS3089C**; 8 MB RAM, 1 GB internal memory | [mPTech specification](https://download.mptech.eu/User_Manual/hammer/hammer-watch-2/HAMMER%20WATCH%202%20-%20specyfikacja.pdf), locally retained and hashed in [web manifest](reports/web-source-manifest.json) | High for published specification; no board inspection |
| H2 | 1.5-inch 466×466 AMOLED, Bluetooth 5.3, 530 mAh; compass, barometer and altitude features advertised | [Official product page](https://hammerphones.com/shop/sma002932-hammer-watch-2-38599), [official manual](https://download.mptech.eu/User_Manual/hammer/hammer-watch-2/Hammer_Watch_2_Instrukcja_obs%C5%82ugi_20241206_PL_EN_CZ_SK_HU_DE_IT_ES_PT_FR_EE_LT_LV_BG_GR.pdf) | High for published product features; not proof of face bindings |
| H3 | Regulatory family links **HAMMER WATCH 2**, **EdgeMate R1**, Creek Wearable, and **2BBYH-C2039** | [Applicant letter mirror](https://manuals.plus/m/822ba8fe06c9caf68fed3d579a391e7a607065ee40282b9540ed6f43803e6241), [filing index](https://fccid.io/2BBYHC2039), [model confirmation index](https://fccid.io/2BBYH-C2039/Letter/Model-Difference-7947275) | Strong OEM lead from indexed regulatory content. Direct FCC attachment retrieval was unavailable; mirror HTML redownload also failed. Exact user's hardware revision unverified |
| H4 | Firmware OS, graphics framework, board revision and sensor chip models remain unknown | No HAMMER firmware image, device-info export or board photos supplied | Unknown; do not label this watch Zephyr/LVGL merely from its chipset |

mPTech is the marketed manufacturer. Creek is the OEM/platform lead. The official chipmaker lists [ATS3089C in its smartwatch family](https://www.actionstech.com/index.php?id=product&siteId=4). No CPU core architecture or clock speed is asserted for the actual HAMMER unit.

## Companion app and acquisition

The [official Google Play listing](https://play.google.com/store/apps/details?id=com.hammerup.app) names mPTech and package **`com.hammerup.app`**, and describes photo-dial settings. Distinguish it from the older **Hammer Watch** (`com.cqkct.youthhealth.hammerwatch`) and **Hammer W+** (`com.zhapp.hammer`). They are not interchangeable evidence.

Preferred legitimate acquisition is Google Play installation followed by extraction of its installed base and split APKs from the user's own phone. A manufacturer-provided APK is another acceptable source if published. The official support page inspected did not provide a direct Android APK. Public-mirror fallback was explicitly selected for this project.

Initially downloaded [APKPure's Hammer App bundle](https://apkpure.net/hammer-app/com.hammerup.app/download) for static inspection. It has since been installed and run only in the isolated Android debug emulator:

| Property | Observed value |
|---|---|
| Version | 1.0.15, versionCode 35 |
| Package | `com.hammerup.app` |
| Bundle | 200,172,218 bytes; 20 APKs, including base and arm64 native split |
| XAPK SHA-256 | `ea1a3ac0f52b7caec7bf5eb15348c7e748e6c0ab77b6bfc0d39ba8e10931b474` |
| Base APK SHA-256 | `e009d398056cc086132f7aa5745a457ebdd40a75935477b9883b259719717231` |
| Extracted signer certificate SHA-256 | `d6b2b309f5dec12e2e3e7d5f811c6157650dd82b52a2fcfeca220939bd7c6a03` |
| Signature verification | All 20 verified using Google apksig 8.13.0; v2/v3, zero errors and warnings |
| Publisher authenticity | **Unverified** until compared with a trusted Play installation |

Evidence: [acquisition manifest](reports/acquisition-manifest.json), [package summary](reports/android-package-summary.json), [independent signature report](reports/apk-signature-verification.json). The SHA-256s were calculated locally, not copied from a mirror's assertions. A regression test modifies a real APK asset and verifies that apksig rejects the tampered file.

## App analysis

**A1 — Creek/Flutter implementation confirmed in the acquired APK.** Base assets include `assets/flutter_assets/`; native split includes `libapp.so`, `libflutter.so`, `libcreekActRes.so` and `libXClz4.so`. The app contains compiled references to `creek_dial_sdk` and the dial JSON model. Android DEX contains `com.actions.actres.ActresPlugin` and `com.actions.actres.ResBuilder`. This is stronger evidence of Creek integration than the shared chipset alone.

**A2 — Catalog path candidates found, request semantics unverified.** The following literal strings occur in `libapp.so`:

- `https://app.hammerphones.com`
- `/service-parts/v1/dial/classify/isUpdate`
- `/service-parts/v1/dial/classify/pb/list`
- `/service-parts/v1/dial/listFirmware`
- `/service-parts/v1/dial/pages`
- `/service-parts/v1/dial/profile`

Their exact offsets and containing library hash are recorded in [native findings](reports/android-native-findings.json). These are **static candidates**: no execution trace associates each path with that host, HTTP method, credentials or parameter schema. At this initial stage they had not been called; subsequent authenticated configuration results are documented below. `/firmware/face-gallery/...` strings also exist but appear to be app navigation routes; they are not presented as download endpoints.

Relevant compiled Dart source identifiers include `creek_app/.../network/request/device/dial_list.dart`, `creek_dial_sdk/dial/dial_tool.dart`, `creek_dial_sdk/dial/model/dial_json_model.dart`, and `creek_dial_sdk/byte_array/byte_array.dart`. Identifiers surviving AOT are not recovered Dart method bodies. JADX can inspect Android wrappers but cannot recover the Flutter implementation by itself.

**A3 — Native image packing boundary identified.** `ActresPlugin.onMethodCall` handles `encodeImage`, obtains `imagePath`, and calls `ResBuilder.addSinglePicture`. Its success branch returns an `.lz4` path. Native exports include `Java_com_actions_actres_ResBuilder_addPicture`, `addSinglePicture`, `isNeedJpegCompress` and `replacePicture`. JNI symbol addresses and library SHA-256 are in the native findings report. JADX output is kept under `private/analysis/ActresPlugin.java`; reproduce it with the README command. LZ4 exports and a `crc32` string are present, but their presence does **not** establish a whole-face container checksum algorithm.

**A4 — Actual HAMMER cache path and download request are unresolved.** Creek's Android demo uses `context.filesDir/directory/<face-name>` before `parseDial`; see `CustomDialScreenViewModel.kt:118–170` at the pinned SDK revision. That is a **demo path**, not a verified HAMMER App cache path. Subsequent authorized emulator analysis accessed local app configuration/session data privately. No physical app data or cached-face replacement has been attempted.

## SDK and existing projects

The pinned [CreekSDK](https://github.com/creekwearable/CreekSDK/tree/085d919da3d02103f490e37a1a5f108132dcf515) revision contains source wrappers, generated protobuf models and example face ZIPs. The pinned [Android demo](https://github.com/creekwearable/androidSDKDemo/tree/582d0732de9dd486fd0e8028aa16010deafb6c0d) and [developer guide](https://github.com/creekwearable/CreekDeveloperGuide/tree/f6fd1e1fce415e1822f39a09299b0cd09f938cf7) provide a direct platform reference.

- Swift `parseDial`, `parsePhotoDial`, `setCurrentFunction`, `encodeDial`, `encodePhotoDial`, `upload`, `getWatchDial`, `setWatchDial` and `delWatchDial` are visible in `CreekSDKExtension.swift`; implementation delegates through a Flutter method channel.
- Android `CustomDialScreenViewModel.installDial` calls `encodeDial` then `uploadNew` with a `.bin` filename. Its parse example selects `JX_3085C_PLATFORM`; do not change that to ATS3089C based on hardware naming alone.
- The developer guide distinguishes prebuilt `.bin` files from composable source `.zip` packs. Compatible catalog selection uses watch firmware/device ID and `plateVersion`.
- `watchdial.pb.swift` describes face names, sizes, installed categories, capacity, version and compression capability. This is useful protocol metadata, not a binary renderer specification.

All retrieved source files have individual hashes and immutable commit URLs in [SDK manifest](reports/creek-source-manifest.json) and [additional source manifest](reports/creek-additional-source-manifest.json).

Related research checked: [Actions LVGL port](https://github.com/lvgl/lv_port_actions_technology), [CMF-Open](https://github.com/TechJeeper/CMF-Open), [CMF Watch Pro 2 protocol](https://github.com/joshuapassos/CMF-Watch-Pro-2-BLE-Protocol), [CMF firmware research](https://github.com/whatotter/cmf-watch-firmware). They are reference leads. No CMF command, firmware image, face encoder or UUID mapping is treated as HAMMER-compatible. No third-party implementation was copied into this toolkit.

## Compatibility and feasibility verdict

**Custom downloadable resources are plausible and supported by the Creek platform's published API; installation of arbitrary files on this exact HAMMER firmware is unproven.** Twelve real Creek source-face archives have been inspected. Most target `ats3085c`; an additional Android example targets `ats3085s` and contains weather and altitude declarations. This establishes that the reference format can describe more than a static photograph. It does not establish which widgets HAMMER accepts.

The desired factory-face modification remains blocked by the missing factory resource or reference, the watch's framework/device identifiers and the absence of a matching compiled face sample. No factory face has been exported. It remains possible that the factory's compass or pressure widgets are firmware-only; that is a hypothesis to test, not a conclusion.

## Follow-up: emulator, AOT and compiler evidence

The user authorized emulator analysis and deferred physical-watch testing. The unchanged app installed successfully, passed first-run setup and reached device search. Its regional configuration service returned application code 401 without credentials; the later user sign-in succeeded, and authenticated configuration now returns code 200. Target catalog acquisition remains gated on verified device compatibility identifiers. A visible emulator/login reminder was opened for the user; credentials are entered directly in the official app, not in chat.

Blutter successfully recovered annotated ARM64 AOT code and object metadata (Dart 3.9.2). This updates A2: `DialListRequest.path` is tied to the pages endpoint, `BaseRequest.httpMethod` is POST, and authority selection uses a regional `serverNode`, defaulting to the Frankfurt Creek host. `app.hammerphones.com` occurs in a share URL and must not be treated as the catalog host. Request-model fields and exact method addresses are documented in `protocol.md` and `reports/aot-method-index.json`.

A permission-stripped SDK 10.7 harness generated two reference BINs without network/Bluetooth access or upload calls. Their 44-byte header, 38-byte index entries, CRC coverage and image codecs were validated against actual outputs. Both reconstruct exactly through the JSON IR. All 147 BGRA images match their source pixels. These are JX_3085C reference outputs; the native-backed mode and actual HAMMER compatibility remain untested. See [format](format.md), [emulator lab](emulator.md) and [compiler results](reports/sdk-compiler-results.json).

The virtual watch remains a discovery-only Netsim prototype. With the authenticated name allowlist and corrected characteristic direction, `HW2` is discovered and connects; two initial app writes were observed. Application pairing and target-face download remain incomplete. Firmware/device ID, factory-face reference and sensor compatibility are still needed before a final watch face can be established.

## User target confirmed — 2026-10-31

The user selected **ADVENTURER**, the default face shown in the first supplied app screenshot. The second screenshot identifies the device as **HW2**, model **2039**, firmware **V2.0.12**. Personal serial/MAC values are intentionally omitted; original screenshots remain ignored under `private/references`. The screenshot is an app/rendered reference, not a live sensor validation.

The Model No. view (`about_watch.view.dart` at `0x324ed80..0x324eda8`) reads controller field_2b. `AboutWatchController.getLocalDeviceInfo` at `0x29c24f8..0x29c2540` fills that with formatted `DeviceModel.field_7`. `FaceGalleryController._getDialMarketFromNet` at `0x2a62c7c..0x2a62d24` uses the same field for the request's firmwareId. This supports **2039** as the catalog firmware ID in the acquired build, rather than treating the regulatory model code alone as proof. Server confirmation remains pending.

A read-only model/color query for that ID returned application **509**, “Account logged in at another location.” The old session is invalidated; the response establishes nothing about this model's catalog or color. No automatic re-login was attempted. A share link from ADVENTURER's share button is the least disruptive next acquisition lead; whether it exposes a usable resource is unverified. Device dial framework (`plateVersion`) and actual face resources remain missing.

A further code check corrected the client schema: `snCode` is an **integer device code**, not the displayed serial-number string (`AllDialListRequestModel.toJson`, `0x227ed14..0x227ed3c`). The gallery uses a default value of 65 when its device field is absent; that fallback is not asserted to be this watch's actual value. Customer code derives from `DeviceSnModel.customerIdToASCLL`; it is also unverified. No personal serial was submitted to the API. See [target evidence](reports/target-adventurer.json).

## ADVENTURER share card examined — 2026-10-31

The supplied share card's QR decoded successfully with `zbarimg`. It leads to `app.hammerphones.com` with a hash route `/code/:key`. The retrieved frontend (`app.2e46cd22.js` and `chunk-dcbf33a8.7d7dde4b.js`) resolves that key through GET `service-manager/v1/app/info/markingDetail` and displays companion-app store/download links. No face identifier or resource URL was recovered. This closes the share-link acquisition lead; it is not a face export. Embedded frontend authorization material was not used.

The raw card includes an account name and stays private. [Sanitized evidence](reports/adventurer-share-findings.json) records artifact hashes and the finding. Next acquisition needs either authorized physical metadata/catalog access through the official app or private app cache/capture samples; a custom face cannot be built from the share image alone. The actual plateVersion and ADVENTURER binary/source remain missing.

## Actual HAMMER catalog resources — 2026-10-31

The user-authenticated official app in the isolated emulator displayed ADVENTURER
and downloaded `ewrcompass_0819@LC.zip`, then compiled it locally. The ZIP metadata
states `platform: ats3089C`, resolution 466×466 and dial version 5. It includes
50 normal widgets, 5 AOD widgets and green/orange palettes associated with source
codes 65/72. These are source declarations, not measured physical device codes.

The original binary is 427,972 bytes, 128 resources, CRC32 `288af9a1`.
SHA-256: `bcb39cc699ffc6289009ef5b23431b76bfa23bbffb6d099afe4c0da095fab84e`.
The isolated Creek SDK 10.7 compiler using its JX_3085C enum produced exactly the
same bytes from this actual `ats3089C` source. This establishes the observed
compiler path for the acquired pack; it does not rename the physical chipset.

Compass, altitude and pressure are explicit widgets, so preserving their dynamic
bindings is feasible at source level. Weather conditions and battery are absent
from this layout. Modular Compact-Weather was acquired as a second real source /
binary pair; its time widget supports the candidate's observed `text/time` schema.
See [hashed evidence](reports/adventurer-acquisition.json) and [compiler validation](reports/adventurer-digital-validation.json).

## First physical metadata and resource write — 2026-10-31

Fresh device inquiries confirm ID2039, firmware2.0.12, 466×466, color72 and SDK
platform enum3. The SDK names enum3 JX_3085S_PLATFORM; this is a protocol/API label,
not evidence that the marketed ATS3089C chipset specification is wrong. The real
watch reports framework8 and lists the downloaded ADVENTURER name/version5.
Platform3/ARM64 offline compilation reproduced the official original exactly.

The official app produced identical original binaries for color65 and color72,
while displaying green and orange catalog previews respectively. Retaining the
original multi-palette metadata is therefore preferred to forcing cur_sn/colors.
The separate test face now installed does so.

After explicit approval, real file-transfer ACKs and prefix-verified continuation
completed a429,383-byte upload. A CRC-valid subsequent inquiry confirms the test
is active and the factory face remains listed. This establishes custom resource
installation on this unit, but not successful HH:MM rendering or live complication
behavior until observed. [Physical evidence](reports/physical-installation-validation.json).

## Physical redraw experiments — 2026-10-31

The user compared factory and test faces on the same unit. Factory compass moves;
revision 1 catches up on minute changes. Revision 3 adds native `text/second` and
removes pressure/altitude; user confirms seconds work but compass remains frozen.
This disproves the claim that any once-per-second text update refreshes compass.
Revision 4 retains original pointer geometry as a further controlled hypothesis.
Its sprite changes, numeric month array and date bindings are offline validated;
physical sensor behavior must be observed separately. No firmware disassembly
has established the scheduling cause. User photo and health values remain private.

Date schema evidence: `circlePhoto/firmware/dial.json` uses `text/day` and the
second acquired compiler reference uses `array/month` with count 12. Revision 4
uses those observed widget types with existing Data glyphs to generate twelve
numeric month images. Indexing and locale behavior remain hardware checks.
