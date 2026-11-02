# Return to Gaming Mode — 1.0.0

[Español](es/return-gaming.md)

Replaces the user's `Return.desktop` and GAMEMODE icon in the menu/desktop, not the system package. Opening it asks whether to close Desktop and return to Gaming. Cancel does not call SteamOS or close anything; save your work before accepting.

If default boot is Desktop it uses `steamosctl switch-to-game-mode`; if Gaming, KDE logout preserves that default. Unknown values/errors stop the action.

Individual: `Volver-al-Modo-Gaming-1.0.0.zip`. Run the `.run` without sudo and select the component. Requires `kdialog`, `steamosctl` and `qdbus6` or `qdbus`. Uninstall via **Desinstalar Return to Gaming Mode**. Original launcher/icon and desktop symlink are restored from the [receipt](INSTALLATION.md). Installation/removal never switches sessions.

Sources: [script](../components/return-gaming/return-to-gaming.sh), [launcher/backup code](../installer/launchers.py), [owner-supplied GAMEMODE icon](../components/return-gaming/GAMEMODE.png), not relicensed as MIT. The icon name intentionally overrides the original. If KDE caches the old icon, run `kbuildsycoca6 --noincremental` in your normal session; no Bluetooth/system restart needed.
