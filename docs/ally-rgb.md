# ALLY RGB — Decky 1.2

[Español](es/ally-rgb.md)

Lighting only for **ASUS ROG Ally RC71L with x86_64 SteamOS**. No TDP, SMT, core/thread, charging, fan, EC or MCU changes. Ally X is not validated.

## Features and use

- Four RGB zones: all, pairs **1–2**, **3–4**, **2–3**, **1–4**, or individually.
- Independent per-zone effects, speed, colors and transitions run simultaneously.
- Static, breathing, rainbow, wave, transition and internal-battery effects.
- Manual red/green/blue channels; transition start/end colors.
- 0–100% channel displays, including both transition colors, retaining all 256 RGB levels.
- Speed 0% (effect minimum) to 100% (maximum), without changing saved timing/values.
- Global brightness/power; the kernel exposes one brightness for all four LEDs.
- Optional **Recuperar al despertar/encender** automatically saves/restores all four zones.

Selecting a zone changes the editor only, not other animations or their phases. Mixed groups show **Varios efectos (conservar)** until explicitly edited. Changes are live; no Apply button. Zones are numbered 1–4 without an unverified physical left/right map. No quick colors/profiles/extra controls/audio-screen sync.

Battery percentage/effect use the internal BAT0, never controllers/peripherals. Internal batteries without `scope` are accepted; `scope=Device` is excluded. Missing data is shown explicitly and no fabricated percentage is applied.

## Install

Choose RGB in the suite or download `ALLY-RGB-1.2.zip`, extract and run `ALLY-RGB-1.2-SteamOS.run` from Desktop without sudo. Nothing selected initially. Requires active Decky, system `python3-aiohttp` and the expected four packed kernel colors. No Loader, Python or driver installation.

The outer ZIP is not Decky's native ZIP. To extract without installing:

```sh
bash ALLY-RGB-1.2-SteamOS.run --extract sources
```

`sources/payloads/ALLY-RGB-1.2.zip` is the native Decky ZIP with top folder `ally-rgb/`. Native Decky ZIP installation is an alternative. The suite checks SHA256, identity/version/manifest, exact request, installed files and backend response. Reconnection does not repeat confirmation. No Steam/other-plugin restarts. Reopen a stale panel, or use native Decky management and restart Steam manually when convenient.

## Recovery and coexistence

Opening/status queries do not change lighting. Fresh installs apply no colors at load. Previously saved settings with recovery enabled restore at Decky load even without opening the panel, retaining off/brightness/all four effects/colors/speeds. Turning recovery off prevents automatic restore but keeps saved settings.

Backend recovery uses light Steam pulses, even with QAM closed. BOOTTIME−MONOTONIC detects sleep; 10 seconds of continuous pulses are required, gaps >4 seconds restart the countdown, and no continuity within 60 seconds skips the cycle. No internal sleep hooks or wall clock dependence. Current profile restores **once, directly, without a forced off/on flash**. Off/zero brightness stays off. Manual edits, a new cycle or unload invalidate pending work; commands are not retried.

All RGB I/O runs in a helper enrolled in transient `ally-rgb-io-*.scope` under `user.slice` **before commands**. Both processes verify cgroup/sleep cycle before each report and reject stale commands. Enrollment is bounded and checks actual PID movement after asynchronous systemd completion.

No permanent logind/clock watcher, persistent services, sleep hooks, inhibitors or freezer changes. Helpers stay with the SteamOS-frozen user session. Timeouts do not kill frozen helpers or allow replacement of an unterminable helper holding its lock; they cannot solve uninterruptible kernel I/O.

Status is cached and neither reads nor writes RGB. Static profiles release worker/flock; animations share one helper. The displayed state is the last known application, so idle external changes may remain unnoticed. The RGB-process-only [Decky #975](https://github.com/SteamDeckHomebrew/decky-loader/issues/975) EOF adaptation does not modify Loader/other plugins or replace native EOF handling.

Do not run another RGB writer. Known HueSync/HHD/Ally Center/asusd/OpenRGB processes cause refusal, not automatic stop/uninstall. Unknown writers/firmware cannot be guaranteed detected. Ally Power is independent; no shared power lock/settings. Closing QAM leaves animations running; backend unload stops its worker without restoring over another manager. Device loss/external state changes yield without reimposition loops or idle RGB polling.

## Upgrade/remove

Suite replacement is refused while RGB controls lights or is paused with pending recovery. Leaving Gaming alone may not stop automatic recovery; disable through Decky and use its native installer rather than expecting the suite to stop it. Recognized inactive installations get a backup at `$XDG_STATE_HOME/steamos-ally-suite/ally-rgb/`, default `~/.local/state`. `DECKY_PLUGIN_DIR` can name a nonstandard plugin parent. Decky settings are retained. Remove through Decky Plugins; no privileged uninstaller is added.

## Kernel interface and verification

Requires `/sys/class/leds/ally:rgb:joystick_rings`, four `rgb` entries in `multi_index`, `max_brightness=255`. Supported kernels use packed RRGGBB `multi_intensity` and brightness. If packed values are clipped to 255, an RGB-only hidraw fallback checks ASUS USB 0b05:1abe interface 02, descriptor and device identity. No kernel/firmware/button/power changes. Installer discovery sends no commands. Python stdlib plus occasional SteamOS `busctl` metadata calls; no pyserial/termios/external HID package installation.

HID success means transport acceptance, not physical color readback. Last sent frame, sysfs/device changes and known managers are tracked, not every unknown HID writer. No driver reinstall.

[Source/guide](../components/ally-rgb/README.md) · [plugin tests](../components/ally-rgb/VERIFICACION.md) · [suite verification](VERIFICATION.md) · [licenses](../components/ally-rgb/THIRD-PARTY.md).

Recorded: 142 automated tests (124 Python + 18 JavaScript), TypeScript/Rollup and real backend/frontend load. User confirmed three Gaming suspend/resume cycles with an emulator open/recovery enabled, plus new pairs/percentages. Not physical color readback, proof of a kernel root cause or universal Ally/SteamOS validation.
