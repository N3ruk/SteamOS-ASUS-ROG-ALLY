# Ally Power — Decky Gaming 1.2

[Español](es/ally-power-decky.md)

TDP, SMT, core/thread controls in Decky's Gaming panel. Requires supported Ally hardware and **Decky installed and active**. Installation does not install/activate Loader or modify Steam.

## Controls

First under **Ajuste manual**, **TDP de Steam desactivado** disables native Steam TDP through Steam's internal interface and enables plugin TDP only after verification. With it off, use native Steam TDP; API failure leaves plugin TDP disabled. **SMT/CPU are independent**. Changes are serialized/live without Apply/Release/Restore. If Steam reclaims native TDP through a profile, the plugin yields rather than competing.

Loading/status queries do not modify hardware. Hardware exclusion is acquired only for requested operations, and known managers block competing writes. Leaving Gaming normalizes CPU still owned, then yields without overwriting another manager. Displayed limits are known configuration, not measured consumption.

## Sleep and optional recovery

Before reducing CPU/SMT, a logind **delay** inhibitor is acquired, not block. Before sleep, SMT/all threads of the still-owned CPU are enabled; TDP, RGB and HID are untouched. Preparation is bounded and always releases the inhibitor. D-Bus helper handles metadata only; CPU/RyzenAdj I/O runs in a verified temporary `user.slice` scope with session/freezer guards. No own services or persistent hooks.

Optional wake recovery remembers owned settings in memory. After **10 seconds** of continuous Steam Gaming pulses, it restores **TDP → CPU/SMT** once, even with QAM closed. CPU stays complete while waiting and protection is reacquired before reduction. TDP respects current battery/charger limits and yields if Steam reclaims it/changes profiles.

Gaps >4 seconds restart the countdown; the attempt expires after 60 seconds. Manual edit, new suspend, game change, leaving Gaming or a competing manager cancels. Unknown game identity waits rather than applying game settings to the menu. No retry loop. Only the switch persists, not profiles; startup/reload applies no CPU/TDP. With recovery off, CPU stays complete after wake until manual action.

## Install, update and remove

`Ally-Power-Decky-1.2.zip` contains a `.run` installer and, inside, the **native Decky ZIP 1.2**, sources/licenses. The outer ZIP is not installed directly into Decky. Extract with `--extract sources` and use the ZIP under `sources/payloads/` for manual installation. Local API checked with Loader 3.3.0; system `python3-aiohttp` required, not automatically installed. Native Decky ZIP installation remains an alternative.

ZIP hash, in-memory local authorization, exact request, registered version and backend response are checked. No tokens printed or Steam restarts. Existing versions must be inactive without pending recovery; a backup ZIP is made first. See [recovery](INSTALLATION.md). Remove through Decky plugin settings; restore backup ZIPs only after releasing hardware control.

## Topology and verification

Distribution, `.run`, native ZIP and catalog all use **1.2**. Includes status/manual controls, `gamescope-wl` detection and stable core/thread limits across SMT toggles.

Verified physical metadata only is kept at `/var/lib/ally-power-decky/cpu-topology.json`, not power profiles or startup settings. This supports restarting the backend with SMT off independently of Desktop; a valid Desktop snapshot is also usable. Incomplete/zero offline IDs are rejected, never assumed new cores. Without a complete identity/snapshot, enable all cores/SMT with your current manager first; the plugin does not enable CPUs to inspect them or distribute another machine's topology.

[Sources](../components/ally-power-decky) · [original guide](../components/ally-power-decky/README.md) · [historical verification](../components/ally-power-decky/VERIFICACION.md). Own MIT code plus RyzenAdj sources/licenses. Recorded checks: 115 Python and 16 JavaScript tests, TypeScript/build, preparation/recovery/cancellations and CPU/TDP independence. The user separately confirmed real preparation and automatic recovery in Gaming before the package refresh. This is not validation on other Ally machines. See [suite verification](VERIFICATION.md).
