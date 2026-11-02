# Build and package

[Español, including historical release-maintenance records](es/BUILD.md) · [Home](../README.md)

## Project sources

Sources for all seven components, assets, tests, pinned original payloads and RyzenAdj corresponding sources/licenses are included. No `node_modules`, credentials, diagnostic references or machine snapshots. Included third-party binaries keep their notices and are not downloaded during installation.

## Build the eight ZIPs

Python 3.10+:

```sh
python3 build.py
python3 -m unittest discover -s tests -v
python3 verify_packages.py
(cd release && sha256sum -c SHA256SUMS)
```

`release/` contains the suite, seven individuals and `SHA256SUMS`. Each ZIP has a self-extracting `.run` independent of the original folder. Fixed file ordering/dates make identical sources/inputs produce identical bytes. SHA256 checks corruption, not cryptographic author identity.

## Rebuild application payloads explicitly

The central build packages pinned installers in `payloads/`; editing `components/` alone **does not change those executables**.

- Desktop: run `python3 build.py` in `components/ally-power`, copy the `.run` from `dist/` to `payloads/`, adjust name/version in suite catalog/build if changed. See its `REBUILD.md`.
- RGB: in `components/ally-rgb`, run `npm ci`, `npm run typecheck`, `npm run build`, `python3 build.py`. Copy native `release/ALLY-RGB-1.2.zip` to `payloads/` and update its pinned hash. Suite build produces the outer individual installer.
- Bluetooth: run its `build.py`, copy the `.run` from `dist/` to `payloads/`.
- Power Decky: in its component, use lockfile-compatible Node/npm; `npm ci --ignore-scripts`, typecheck/build, then `python3 build.py`; copy the native ZIP to `payloads/`.
- Launchers: packaged directly from their component sources and `installer/launchers.py`; no compilation.

Review replaced payloads before updating their entries in `payloads/SHA256SUMS`; never regenerate hashes to conceal corruption. Rebuild the suite to refresh manifests, installers, ZIPs and checksums. Tests do not write TDP/SMT or switch real boot mode.

## Collection 1.3 / video 1.0

```sh
(cd components/video-output-ally && npm ci --ignore-scripts && npm run typecheck && npm run build)
(cd components/video-output-ally && python3 -m unittest discover -s tests -v && node --test tests/frontend.test.mjs)
python3 components/video-output-ally/build.py
# Review/copy its native release ZIP to payloads/ and update that pinned hash.
python3 build.py --only central video-output-ally
python3 -m unittest discover -s tests -v
python3 verify_packages.py
(cd release && sha256sum -c SHA256SUMS)
```

Selective build needs the six existing individual ZIPs in `release/`; download and verify those from v1.2 to preserve their exact bytes. A fresh checkout can run the full build instead, possibly changing wrappers/docs of unchanged applications. Central and video individual contain the same native `output-manager/` ZIP and source. No host EDID/settings/wrapper is distributed. npm licenses and original BSD-3-Clause provenance are retained.

Suite version is in `installer/version.py`; video version in its root package/lock/backend/catalog. Do not globally replace 1.2: POWER/RGB remain 1.2. The source extracted from an individual contains only its component; rebuild all packages from a full checkout or central source extraction.

## Component tests

Use system Python; graphical apps need GTK4/PyGObject:

```sh
(cd components/ally-power && PYTHONPATH=src:packaging:. python3 -m unittest discover -s tests -v)
(cd components/ally-power-decky && python3 -m unittest discover -s tests -v)
(cd components/ally-power-decky && node --test tests/test_live_queue.mjs tests/test_steam_tdp.mjs tests/test_session_frontend.mjs)
(cd components/ally-rgb && python3 -m unittest discover -s tests -v)
(cd components/ally-rgb && node --test tests/test_queue.mjs tests/test_ui.mjs)
(cd components/bluetooth-trust-manager && python3 -m unittest -v test_installer)
(cd components/bluetooth-trust-manager/payload && python3 -m unittest -v test_app)
```

## Release publication

`publish.py` needs authenticated official GitHub CLI and explicit visibility. Build/tests do not publish. On a reviewed, clean `main` checkout:

```sh
gh auth login --hostname github.com --git-protocol https --web
python3 publish.py --owner YOUR_ACCOUNT --visibility public
```

It verifies eight packages, creates the repo if absent, preserves unrelated remotes, pushes without force and creates v1.3 with eight ZIPs plus checksums. Published downloads are checked against local hashes. It does not replace existing releases. Repo creation requires additional GitHub permissions beyond existing-repo write access. Preserve v1.2/v1.0.0 tags/releases and unchanged individual assets.

The [Spanish historical guide](es/BUILD.md) retains the full RGB/POWER v1.2 selective-refresh records. Those describe already-authorized historical maintenance, not permission to replace releases or skip real hardware validation. Documentation-only commits do not require repackaging existing assets.
