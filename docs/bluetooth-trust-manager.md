# Bluetooth Trust Manager — 1.0.0

[Español](es/bluetooth-trust-manager.md)

Lists **trusted** Bluetooth devices, filters by name/address and removes trust from one exact device after confirmation showing its address.

Useful for **PS3/Sixaxis controllers**: BlueZ may retain trust after unlinking and skip USB authorization. Removing trust and reconnecting USB may restore the authorization prompt. Accept, unplug and press PS to test Bluetooth. It does not guarantee repair of every pairing issue or compatible/clone controller.

Only the selected device's `Trusted` property changes. It does **not** delete keys, call `RemoveDevice`, disable Bluetooth or remove other devices. This is not a general pairing manager.

Individual package: `Confianza-Bluetooth-1.0.0.zip`, or central suite. Reuses the original `.run` without application changes. Requires SteamOS KDE, Python/PyGObject GTK4, BlueZ and D-Bus; no sudo. Close the app before reinstalling. User-only installation/removal does not query/change controller trust. Use its uninstall menu entry or original `.run --uninstall`; a recoverable copy is kept.

[Sources](../components/bluetooth-trust-manager) · [original Spanish guide](../components/bluetooth-trust-manager/LEEME.md). Code/controller SVG are MIT under their license. Uses the system BlueZ D-Bus API, not a new suite service.
