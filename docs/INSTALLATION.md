# Installation, upgrades and recovery

[Español](es/INSTALLATION.md) · [Home](../README.md)

## Normal installation

Download the central or individual ZIP, extract it, allow the `.run` to execute and start it from Desktop Mode without sudo. No repository clone or Internet dependency download is needed.

The GTK4 window provides descriptions/check boxes. KDialog is used if GTK4 is unavailable; a terminal without a graphical session offers text selection. Missing dependencies are reported, not installed through pip/pacman or system changes.

The window stays busy for each operation and reports a result per component. A failed component does not uninstall successful ones or prevent attempts on other selected components. Cancel in the application's own dialog if desired; an original installer may return 0 on cancellation, and the result explicitly says so.

## Files and permissions

- Launchers: `$XDG_DATA_HOME/applications` and `$XDG_DATA_HOME/steamos-ally-suite/<component>`; icons under `icons/hicolor`. Default: `~/.local/share`.
- Return to Gaming also updates `Return.desktop` on the desktop resolved by `xdg-user-dir DESKTOP`.
- Backups/receipts: `$XDG_STATE_HOME/steamos-ally-suite/<component>/receipt.json`, default `~/.local/state`. Receipts retain original/new contents, not just names.
- Ally Power Desktop: `/usr/local/lib/desktop-power`, commands in `/usr/local/bin`, user shortcuts. Its own installer preserves backups and restores SteamOS read-only mode if temporarily disabled.
- Bluetooth: `~/.local/share/bluetooth-trust-manager` and user shortcuts; respects `XDG_DATA_HOME`.
- Decky: delegated to Loader's plugin mechanism. Steam, Bluetooth and other plugins are not restarted.

Launcher writes are atomic per file with exception rollback, **not** power-loss-safe transactions across files. Symlink parent directories are rejected; a final launcher symlink is backed up/restored correctly.

## Upgrade

Run the selected package again. Launchers retain the first-install originals; manually changed managed files are not overwritten. If XDG/desktop paths changed, uninstall using the original paths first.

Close Ally Power, including its tray, or Bluetooth Trust Manager before updating; the suite does not close them for you.

For Decky, leave Gaming so the plugin stops controlling hardware. The adapter checks `get_state.active`, pending recovery and a recognized version, then creates a backup ZIP. Unreadable/missing plugin paths block upgrades. For nonstandard locations set `DECKY_PLUGIN_DIR` to the parent of `ally-power-decky`, `ally-rgb` or `output-manager`. The local API was checked with Loader **3.3.0**; changes produce an error instead of forced restarts/root copies. The WebSocket connection may briefly replace the frontend connection, which reconnects.

## Uninstall

- **Launchers:** use their uninstall menu entries. Original files are restored, or added files removed; recoverable `removed-*.json` receipts remain. Manual changes block replacement. Empty directories/`operation.lock` may remain; these are not running processes.
- **Ally Power / Bluetooth:** menu uninstaller or the original `.run --uninstall`.
- **Decky:** Decky Settings → Plugins → the component → Uninstall. No second privileged uninstaller is added.

Removing the boot launcher does not change the chosen default mode. Removing the Gaming launcher does not change the current session. Review system-update changes before restoring; never overwrite blindly.

## Multiple managers

Desktop and Decky variants can coexist but must not control hardware simultaneously. Close Desktop before Gaming. Detectable competing managers cause refusal; they are not uninstalled, disabled or stopped. Installation does not acquire TDP/SMT control.

## RGB and video

[ALLY RGB](ally-rgb.md) is offered only with a compatible RC71L RGB interface, active Decky and aiohttp. It does not replace a backend controlling lights or paused with pending recovery; leaving Gaming alone is insufficient. Recognized inactive versions are backed up under `$XDG_STATE_HOME/steamos-ally-suite/ally-rgb/`. Disabled plugins should be updated with Decky's native installer. Previously enabled recovery may restore saved lighting after readiness confirmation and 10 seconds; fresh installs do not apply lights. The suite sends no colors and stops no RGB managers.

[Video Output ALLY for DOCKs 1.0](video-output-ally.md) requires RC71L/video prerequisites and active Decky. Install from Desktop; owned/busy/Gaming or restricted states block replacement. Recognized versions/settings are preserved. The internal folder remains `output-manager`: remove original Output Manager through Decky before a new installation. Unknown folders are not overwritten. Both packages contain the same native ZIP, install no Gamescope wrapper, impose no AOC/other monitor on clean installs, do not alter audio and do not switch displays to test installation. Existing video preferences may still apply in Gaming.
