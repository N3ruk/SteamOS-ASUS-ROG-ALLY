# Video Output ALLY for DOCKs

Video-only Decky panel for choosing the Gaming Mode display on an ASUS ROG Ally
with a dock. Maintained by **N3ruk** as a derivative of Output Manager; see
[NOTICE.md](NOTICE.md) and the preserved [BSD-3-Clause license](LICENSE).

## Interface

- One **Salida de vídeo** panel with connected, non-hidden displays.
- Internal screen: **ASUS ALLY**.
- External displays: saved custom label, otherwise EDID manufacturer/model;
  connector name only if monitor information is unavailable. Identical external
  names receive a connector suffix to distinguish them.
- Active outputs, switching progress and errors are visible. Selection remains
  Gaming-only; the Desktop panel is read-only.
- No audio selector or audio commands; no Manage Outputs, Settings or About pages.

Legacy labels, hidden flags, default display identity and other saved settings
are retained. Old audio fields remain inert for recovery/rollback, never applied.
The installed directory stays `output-manager` intentionally: this preserves
settings and the existing Gamescope startup helper path, while the visible Decky
name and frontend API identity use the new application name. Only one controller
must be installed. Plugin version: **1.0**, introduced in the SteamOS ASUS ROG ALLY **1.3** collection.
The plugin and collection versions are independent.

## Video selection and recovery

Architecture: `edid-mst-nudge-v1`, unchanged from the preceding local repair.
The preferred monitor is identified by its verified base EDID hash, not a changing
DP number. Existing display preferences are retained. On a clean install there is no preferred
monitor: choose the display manually. Removing the Settings page
does not change that preference or add new automatic policies. Maintenance APIs
`get_config`/`set_config` remain for compatibility; they are not exposed as a page.

Only in Gaming: 10 seconds of session continuity and 2 seconds of stable cached
DRM topology precede one attempt per topology. Late dock arrival and connector
renumbering are detected by read-only metadata observation every 2 seconds.
Manual selection takes precedence for the current session/suspend cycle.
The existing startup wrapper waits at most 1 second for display identity discovery;
later arrival is handled by the plugin. That wrapper is not changed by the UI
adaptation, including its pre-existing audio EDID wait.

A short-lived helper is enrolled and verified in a transient `user.slice` scope
before any hardware request. It checks suspend epoch, freezer, logind and Gaming
ownership before writes. It uses generic DRM connector `status` off/detect and
native `GAMESCOPE_DISPLAY_MODE_NUDGE`, **not** AMD debugfs hotplug.
`gamescopectl` must confirm the selected connector and DRM must report it enabled.
The internal screen is never forced off. Same-GPU switching only; unverified or
ambiguous identities fail closed. This is not a fix for independent DPCD/link errors.

On errors, only still-matching owned changes are reverted while awake in the same
Gaming cycle. Desktop/unload releases owned restrictions and sends a normal DRM
card change notification so KWin retains its saved layout. No persistent service,
sleep inhibitor, kernel, EDID, power or audio policy is added. If a helper cannot
exit, no second hardware writer starts. Abrupt Loader termination or a kernel
stall cannot guarantee cleanup; kernel force flags reset on reboot.

## Source layout

| File | Responsibility |
| --- | --- |
| `src/index.tsx` | New video-only panel, bounded refresh lifecycle, busy/error handling |
| `main.py` | Small Decky adapter and compatibility configuration API |
| `display_names.py` | Presentation-only EDID labels, cached by monitor identity |
| `settings_store.py` | Atomic settings updates preserving unrelated fields |
| `video_runtime.py` | Existing serialized controller and session/suspend scheduling |
| `video_selector.py` | Existing guarded native selection, verification and rollback |
| `video_startup.py` | Existing bounded read-only startup preference resolver |

Name discovery reads cached kernel EDID only, never DDC/I²C or a connector reprobe.
Common brands have short labels; other manufacturers use the installed hwdata PNP
registry when available, or their three-letter EDID manufacturer code. No online
lookup is performed. Name presentation never changes the EDID selection identity.

## Build and verification

```sh
npm ci --ignore-scripts
npm run typecheck
npm run build
python3 -m unittest discover -s tests -v
python3 -m py_compile main.py settings_store.py display_names.py video_*.py
python3 build.py --out /path/to/local-evidence
```

Install the generated ZIP through Decky's native local installer. For the first
rename, finish unloading/uninstalling **Output Manager** through Decky, retaining
its settings, BEFORE requesting installation of this package into the same directory. Keep a backup beforehand; do
not run both names simultaneously or restart Loader/other plugins unnecessarily.
Only runtime files, documentation and licenses enter the ZIP.

A native `video_probe` verifies the short-lived scope and reads connector metadata
without changing displays. Automated checks do **not** prove physical Gaming
routing: the user must validate the actual dock/display selection in Gaming Mode
before considering physical compatibility verified. Publication does not replace
that end-to-end validation. The installer does not modify the Gamescope startup
wrapper; the startup helper only serves existing compatible integrations.

## Implementation references

- ValveSoftware/gamescope `src/steamcompmgr.cpp`: native display-mode nudge.
- torvalds/linux `drivers/gpu/drm/drm_sysfs.c`: generic connector off/detect.
- KDE/kwin `src/backends/drm/drm_backend.cpp`: normal DRM change notification.
