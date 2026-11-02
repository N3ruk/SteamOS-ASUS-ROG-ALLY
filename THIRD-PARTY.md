# Licenses and provenance

[Español](THIRD-PARTY_ES.md)

## Original code

The central installer, new launcher installers, original scripts/tests/docs are MIT: [LICENSE](LICENSE). Ally Power, its plugin, ALLY RGB and Bluetooth Trust Manager retain MIT notices in their directories. The Bluetooth controller SVG is covered by its original license.

## Supplied icons

`GAMEMODE.png`, `steamos-default-mode-toggle.png` and `icon-gaming.png` are supplied project assets. They are **not** assigned the code's MIT license and this documentation grants no third-party trademark/design rights. They are preserved as provided; no Valve/ASUS/Sony affiliation is implied.

## RyzenAdj

Upstream: https://github.com/FlyGoat/RyzenAdj, version 0.19.0. Official x86_64 binary and full corresponding source are included in Ally Power/Decky with LGPL-3.0/GPL-3.0 notices as applicable. See their `THIRD-PARTY.md`, licenses and sources; suite MIT does not override them.

Pinned official inputs:

- `ryzenadj-manylinux_2_28-x86_64.tar.gz`: `d04547f111c6af3e40d3f210468adb884561618ddade0b640d90e50c88d03444`.
- `RyzenAdj-v0.19.0-source.tar.gz`: `d1998b6c2d1b564f5d43c786cbf764ca9a1d8bb213e2001f98f611ead3087c7e`.

## Platforms and libraries

- Decky Loader/template: https://github.com/SteamDeckHomebrew/decky-loader and https://github.com/SteamDeckHomebrew/decky-plugin-template. Local API checked with Loader 3.3.0; Loader is neither distributed nor installed by the suite.
- Decky frontend dependency versions/licenses are pinned in each component's package-lock. TypeScript source is retained and npm build supported. No `node_modules`; npm notices under component `licenses/npm/`, also included in native ZIPs.
- GTK/PyGObject, BlueZ, KDialog, steamosctl and system libraries come from SteamOS, not private bundled copies.
- Suite Decky adapter uses system aiohttp, not bundled/automatically installed.
- POWER 1.2 includes MIT dbus-next 0.2.3 in `components/ally-power-decky/vendor/dbus_next`, license `licenses/dbus-next-LICENSE`. Only its system-Python metadata helper imports it for logind/delay inhibition; no dependency installation or CPU/TDP/HID access there.

The suite reuses existing installers and native Decky installation rather than adding another privileged installer. Its own UI implements component selection/grouping.

## ALLY RGB

Own MIT code; Decky dependencies pinned in `components/ally-rgb/package-lock.json`, Python/TypeScript source and license notices retained. React/UI supplied by Decky; no node_modules. Ally ABI/HueSync references and full notices: [component THIRD-PARTY](components/ally-rgb/THIRD-PARTY.md). No HueSync, pyserial, HID driver or power-manager code is included.

The original notice records pure-Python MIT dbus-next 0.2.3 under `components/ally-rgb/vendor/dbus_next`, with `components/ally-rgb/licenses/dbus-next-LICENSE`; this does not install system dependencies. Current behavior/observer limits are documented in the [RGB guide](docs/ally-rgb.md).

## Video Output ALLY for DOCKs 1.0

BSD-3-Clause derivative of [Output Manager by joeatethebeans](https://github.com/joeatethebeans/OutputManager). Copyright 2026 joeatethebeans, original 2022–2024 Steam Deck Homebrew, adaptations 2026 N3ruk. Terms/notices/disclaimer retained in `components/video-output-ally/LICENSE` and provenance in NOTICE.md. Installer MIT does not change this license; no ASUS/Valve affiliation.

Includes a new video-only TypeScript panel, configuration/EDID naming adapter and local verified-selection engine. Source/lockfile accompany the package, npm licenses under the component and native ZIP. React/UI and hwdata come from Decky/system without copying their databases or shipping node_modules. No user settings/EDIDs are distributed.
