# Toggle SteamOS default boot mode — 1.0.0

[Español](es/default-mode.md)

Installs **Alternar arranque de SteamOS** and its icon. Each launch toggles the default **Gaming → Desktop** or **Desktop → Gaming**, reads state, runs `steamosctl set-default-login-mode`, verifies and reports the result.

It does not change the current session or reboot. **Installation itself does not change boot mode**. The launcher preserves the original immediate-toggle behavior without a prior confirmation; it reports the selected mode afterward.

Individual package: `Alternar-Arranque-SteamOS-1.0.0.zip`. Requires SteamOS, `steamosctl` and `kdialog`; no sudo. Appears in KDE's menu. The uninstall menu entry restores original files but does not change your chosen boot mode; toggle again before uninstalling if needed.

Sources: [script](../components/default-mode/toggle-default-mode.sh), [launcher/backup handling](../installer/launchers.py), [owner-supplied icon](../components/default-mode/steamos-default-mode-toggle.png), not relicensed as MIT. Paths use the destination user, not hardcoded `/home/deck`.

Missing `steamosctl` or unknown state produces an error, never a guess. Future SteamOS tool changes are not bypassed by replacing system services.
