> **Live installation suspended:** revision 7 has a reported reboot, skipped
> seconds and slow compass. Keep the factory face active for a stability baseline.
> Revision 8 is an offline-only crop correction, not an accepted installable build.

# Face resources

Proprietary samples and generated vendor assets stay under ignored `faces/local/`.

Actual official-app downloads now include ADVENTURER (`ewrcompass_0819@LC`,
`ats3089C`, two palettes) and Modular Compact-Weather (`ewr01_compass_4`).
Their source ZIPs and compiled BINs are retained under `local/adventurer/`.

`local/adventurer/vendor-digital-orange.bin` is the offline vendor-compiled
ADVENTURER digital candidate. It is not a hardware-validated final face.
`local/adventurer/digital-orange/` holds the Python-produced binary, readable JSON
and checks. All 127 non-layout resources are preserved. The original analog
preview assets remain stale. No physical installation or live test has occurred.

Earlier generic SDK reference packs remain useful comparisons; their platform
labels must not substitute for actual target evidence. See [status](../STATUS.md)
and [validation](../reports/adventurer-digital-validation.json).

The preferred physical-test input is now **`local/adventurer/ewr24digital.bin`**,
a separately named vendor-compiled face with original multi-palette selection.
It preserves the factory filename/entry and all 127 non-layout resource hashes.
Earlier same-name and forced-color variants are diagnostic artifacts. No physical
upload or rendering acceptance has occurred. See the prepared plan and STATUS.md.

The real watch has now accepted and activated `ewr24digital.bin` after explicit
approval. Original ADVENTURER remains present. This supersedes the earlier
"no physical upload" status; visual and live-complication acceptance is pending.

Current revision 7 source preparation (private samples required):

```sh
.venv/bin/python -m tools.adventurer_source --revision 7 \
  --source faces/local/adventurer/source \
  --destination faces/local/adventurer/revision7-rebuild-source
.venv/bin/python -m tools.sdk_compile_reference \
  --source faces/local/adventurer/revision7-rebuild-source \
  --destination faces/local/adventurer/revision7-rebuild.bin \
  --platform JX_3085S_PLATFORM --abi arm64-v8a
.venv/bin/python -m tools.watch_face_install --revision 7 \
  --candidate faces/local/adventurer/revision7-rebuild.bin
```

These commands prepare, compile and validate only. They do not install. Existing
destinations are refused. Original samples, font dependency and offline emulator
setup remain necessary; vendor assets are not supplied by this repository.

Generate the disconnected diagnostic controls (local original/weather sources
and the Polish font dependency required):

```sh
.venv/bin/python -m tools.offline_experiments \
  --source faces/local/adventurer/source \
  --destination faces/local/adventurer/offline-controls-rebuild
```

This creates three source packs only below ignored `faces/local`, rejects existing
destinations, preserves base asset hashes, and does not access an emulator or
Bluetooth. To compile a selected control, pass its source directory to the existing
isolated `tools.sdk_compile_reference` command. Do not install the resulting
artifacts: runtime investigation is suspended pending a later stability review.
