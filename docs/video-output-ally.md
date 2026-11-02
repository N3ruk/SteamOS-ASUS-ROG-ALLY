# Video Output ALLY for DOCKs 1.0 — Decky

[Español](es/video-output-ally.md)

Added in **SteamOS ASUS ROG ALLY 1.3**. Select the Gaming display from QAM on an ASUS ROG Ally RC71L with a dock. Does not change audio, TDP, CPU/SMT, lighting or dock firmware.

## Features and requirements

- Video-only panel; no Manage Outputs, Settings, About or audio selector.
- Internal display labeled **ASUS ALLY**; external displays use saved labels or EDID manufacturer/model, falling back to connector names. Duplicate names are distinguished.
- Active-output/progress/error status; Desktop Mode is read-only.
- Existing labels/preferences retained. Fresh installs impose no monitor choice and distribute no builder EDID/settings. Maintenance API retains prior video configuration; no new settings page.

Requires x86_64 SteamOS, RC71L with AMDGPU/Gamescope, installed **active** Decky, system Python3/aiohttp, gamescopectl, xprop, busctl, runuser and pgrep. Dependencies/Loader are not installed automatically. Other models, docks and SteamOS versions need validation. Plugin version is **1.0**; suite **1.3**; POWER/RGB remain 1.2.

## Install, update and recover

Download `Video-Output-ALLY-for-DOCKs-1.0.zip` or suite 1.3. Extract/run its `.run` from Desktop without sudo. Nothing starts selected. Individual contains only video; central offers seven independent choices.

Uses Decky's native installer with exact hash/request. Upgrades require a recognized backend outside Gaming without retained outputs/pending operation. Backups go to `$XDG_STATE_HOME/steamos-ally-suite/output-manager/`. Other plugins/Steam/Loader are not stopped/restarted. Reconnection never resends confirmation. Version, backend response and installed bytes are checked; a per-user lock blocks simultaneous video installs.

For manual Decky installation, extract with `--extract sources` and use `sources/payloads/Video-Output-ALLY-for-DOCKs-1.0.zip`, whose top folder is `output-manager/`, **not** the outer installer ZIP.

Remove original **Output Manager** through Decky first, retaining settings, and wait for completion. Unknown folders are not overwritten and two controllers are not run together. Internal name stays `output-manager` for settings/existing startup-helper compatibility; visible name is Video Output ALLY for DOCKs. Recognized adaptation versions 1.4.0 local / 1.0 can update with backup.

Remove through Decky Settings → Plugins. Backup ZIPs can be installed natively. Old audio fields stay inert for recovery, never applied. Installer modifies no Gamescope wrapper and adds no boot services.

## Display selection/recovery

`edid-mst-nudge-v1` verifies EDID/connector ID, serializes control and enrolls a temporary helper in `user.slice` before I/O. Gaming, freezer, sleep cycle and logind are checked; no AMD trigger_hotplug or physical dock HPD/reset. Gamescope and DRM must confirm the output; failure rolls back only still-recognized own changes. The internal display is never forced off. Physical DPCD/link faults are not guaranteed repaired.

Existing preferences wait for 10 seconds of continuous Gaming and 2 seconds of stable topology, one attempt per topology. Two-second observation reads kernel metadata only. Manual choice wins for the cycle. Desktop/unload releases only own restrictions and notifies KWin without replacing its saved layout. Existing compatible integrations can use the startup helper; installation adds no wrapper/monitor preference.

## Sources and checks

[Sources](../components/video-output-ally): TypeScript, Python, tests and lockfile. BSD-3-Clause derivative of Output Manager with original copyrights/credits in LICENSE/NOTICE. Renaming does not remove provenance or imply ASUS, Valve or upstream endorsement.

Recorded: 53 Python + 5 frontend tests, TypeScript/Rollup, native no-write scope probe on RC71L; panel/backend load and AOC/Acer/ASUS ALLY labels. Simulations/loading **do not validate** physical Gaming monitor switching, late docks/reconnection or other hardware. Packaging tests do not change displays or suspend the computer.
