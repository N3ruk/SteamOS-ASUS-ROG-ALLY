# Video Output ALLY for DOCKs

- Publication and suite integration were authorized by Carlos on 2026-10-31: plugin 1.0, collection/release 1.3. Preserve previous releases and component versions.
- Preserve upstream BSD-3-Clause license/credits. The user-authorized adaptation replaces the frontend and removes audio handling and management/settings/about pages; preserve the video engine logic.
- Video selection is EDID identity + connector-ID validated, serialized, bounded and Gaming-only. No AMD trigger_hotplug, physical dock HPD, kernel/EDID/audio/power changes.
- Hardware writes only in a verified transient output-video scope under user.slice; check sleep epoch, freezer and logind before writes. Never use real display mutations as unit tests.
- Queries only read cached sysfs metadata. Default identity is authoritative; connector name is a UI hint. Manual selection overrides automatic selection for the current session/suspend cycle.
- Native compositor notification is GAMESCOPE_DISPLAY_MODE_NUDGE on primary Gamescope Xwayland; verify the active connector with gamescopectl plus DRM enabled state. No success based solely on a write returning 0.
- On Desktop/unload, release only still-owned force flags and send a normal DRM card change event for KWin. Preserve original layout/refresh/audio/EDID and never reset all connectors indiscriminately.
- Keep backups/evidence outside the runtime ZIP. Use the native Decky local installation flow, compare installed bytes and bundle, and do not restart Loader or other plugins.
- Run python3 -m unittest discover -s tests -v, python3 -m py_compile main.py video_*.py and bash -n on the wrapper. Distinguish simulated tests/native read-only probe from real Gaming success.

- Renaming the visible Decky plugin while retaining its directory: fully finish native removal of the old name before requesting a new install prompt. Do not leave a confirmable new prompt open while old uninstall is still stopping/removing the folder; concurrent confirmation can cause the old uninstall to delete newly extracted files. Same-name updates use the native update flow. Preserve settings and verify final disk bytes, frontend HTTP and native probe after any rename.
