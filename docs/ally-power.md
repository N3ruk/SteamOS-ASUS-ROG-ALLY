# Ally Power — Desktop 1.0.0

[Español](es/ally-power.md)

Manual **TDP, SMT, core and thread** controls in a desktop/tray application, without PowerTools. The original package includes RyzenAdj 0.19.0 and corresponding sources/licenses.

The installer checks x86_64 SteamOS, ASUS ROG Ally RC71L / Ally X RC72LA and AMD Ryzen Z1/Z1 Extreme. Model checks are not physical validation of every variant.

## Installation and use

Use `Ally-Power-Escritorio-1.0.0.zip` or select it in the suite. Its `Ally-Power-1.0.0-SteamOS-x86_64.run` is rebuilt from the included sources. System authorization is requested without storing your password. Close the app and tray first. Installs application/helper under `/usr/local`, without permanent application services or applying settings during installation.

Dependencies include Python/PyGObject GTK4, `pkexec`, `kdialog`, system utilities and RyzenAdj libraries. The installer does not modify SteamOS through pacman.

Open Ally Power from the menu and use its existing **Apply** behavior; live changes are a Decky-plugin feature, not a change to this desktop app. The authorized helper limits writes to CPU/TDP and shares `/run/desktop-power.lock` with Decky.

Do not use it alongside another power/SMT manager. Normal close retains the last settings; a controller failure may restore domains still owned. Close the app before Decky Gaming. Unknown external managers cannot be guaranteed neutralized.

## Actual power and topology

**Estado actual** updates **Consumo global actual: XX.X W** every two seconds from internal BAT0/BATn discharge, not configured TDP or a controller battery. It uses microwatts or current × voltage. Charging/not discharging/missing data are shown as status, never charging power mislabeled as consumption. This read does not change Apply, limits, SMT or close behavior.

The distribution filename remains 1.0.0 and includes corrected physical topology discovery. The installer creates protected `/usr/local/lib/desktop-power/cpu-topology.json` on the destination computer, not the builder. Unprivileged UI then retains correct limits with SMT/cores offline. A fresh install with unidentifiable offline CPUs stops without replacing the existing installation and asks you to enable all cores/SMT using your current manager first. It does not change hardware to inspect topology.

## Removal and sources

Use the menu uninstaller or `bash Ally-Power-1.0.0-SteamOS-x86_64.run --uninstall`; a recoverable copy remains. SteamOS updates may replace `/usr/local`, so keep the installer.

[Source](../components/ally-power) · original Spanish [LEEME](../components/ally-power/LEEME.md), [REBUILD](../components/ally-power/REBUILD.md), [third-party notices](../components/ally-power/THIRD-PARTY.md). Own code MIT; RyzenAdj retains its LGPL/GPL component terms and corresponding sources. Supplied PNG is excluded from MIT.
