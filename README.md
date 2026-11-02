# SteamOS ASUS ROG ALLY 1.3

**English** | [Español](README_ES.md)

An **optional centralized installer** with seven independent components, documentation and individual packages. It does not install or depend on OpenClaw.

## Download and install

[Release 1.3](https://github.com/N3ruk/SteamOS-ASUS-ROG-ALLY/releases/tag/v1.3) provides **eight ZIPs**: the central suite and one per component. Each contains a self-contained `.run` installer with source, licenses and documentation.

1. Extract the ZIP in Desktop Mode.
2. If necessary, allow the `.run` to execute under Properties → Permissions.
3. Run it **as your normal user, without sudo**.
4. Read the descriptions, select only the components you want and click **Instalar seleccionados**. All choices start unchecked.

The central installer does not change boot mode, TDP, SMT or Bluetooth devices during installation. Ally Power and Bluetooth retain their own dialogs; Ally Power requests system authorization.

Collection **1.3** adds **Video Output ALLY for DOCKs 1.0**. Other components keep their existing versions/packages.

## Components

| Component | Purpose | Administrator access | Compatibility |
| --- | --- | --- | --- |
| [Return to Gaming Mode](docs/return-gaming.md) | Custom icon and confirmation before leaving Desktop Mode | No | SteamOS KDE with `steamosctl` |
| [Toggle default boot mode](docs/default-mode.md) | Choose Desktop/Gaming for the next boot | No | SteamOS with `steamosctl` |
| [Ally Power Desktop](docs/ally-power.md) | TDP, SMT, cores and threads | Installation/helper | Ally/Ally X Z1/Z1 Extreme |
| [Ally Power Decky](docs/ally-power-decky.md) | The same hardware domains in Gaming, with live controls | Existing Decky API | Compatible Ally; Decky installed **and active** |
| [ALLY RGB](docs/ally-rgb.md) | Four independent lighting effects, colors/speeds and optional resume/start recovery | Existing Decky API | Ally RC71L, supported RGB kernel interface, active Decky |
| [Video Output ALLY for DOCKs](docs/video-output-ally.md) | Gaming display selection, monitor names and internal ASUS ALLY display; video only | Existing Decky API | Ally RC71L, Gamescope/AMDGPU, active Decky |
| [Bluetooth Trust Manager](docs/bluetooth-trust-manager.md) | Remove trust without deleting pairings; useful for PS3 controllers | No | SteamOS KDE with BlueZ and GTK4 |

**Power controls are not universal**: limited to RC71L/RC72LA, AMD Ryzen Z1/Z1 Extreme and x86_64 SteamOS. ALLY RGB requires RC71L and the four-zone LED interface; Ally X is not validated. Launchers/Bluetooth do not require an Ally model. Compatibility with every past/future SteamOS version is not promised.

## Design choices

- Nothing selected initially; no hidden installations/downloads.
- Decky components are offered only when Loader is installed/active and requirements are met. Loader is never installed or enabled silently.
- Original launchers, including symlinks, are backed up before replacement. No writes to `/usr/share/applications`.
- Desktop and Decky share hardware exclusion; other managers are not stopped. Process/lock checks cannot guarantee detection of firmware or unknown managers.
- Decky's **TDP de Steam desactivado** switch is first under Manual adjustment and enables only plugin TDP. SMT/CPU are independent. Live changes, without Apply/Release/Restore buttons.
- Ally Power prepares the CPU it still owns before sleep. Optional recovery waits for 10 seconds of stable Gaming, then reapplies TDP followed by CPU/SMT once; no startup profiles.
- ALLY RGB handles lighting only; selecting another zone does not stop its effects. Saved lighting can recover at load when explicitly enabled.
- Video Output retains verified display selection/rollback, removes audio controls, installs from Desktop and is not replaced while controlling displays.
- SHA256 is checked before invoking each payload. This detects corruption, not author identity.
- No telemetry or uploading device/configuration data. Decky integration uses `127.0.0.1:1337` only, with a token held in memory.

## Check without installing

```sh
bash SteamOS-ASUS-ROG-ALLY-1.3-SteamOS.run --check
bash SteamOS-ASUS-ROG-ALLY-1.3-SteamOS.run --verify
bash SteamOS-ASUS-ROG-ALLY-1.3-SteamOS.run --extract sources
```

`--check` lists eligible/unavailable components without starting applications or touching hardware. Exit 0 means at least one eligible component; 1 means none or an integrity error. `--verify` checks integrity only.

## Documentation and source

- [Installation, upgrades and recovery](docs/INSTALLATION.md) · [Español](docs/es/INSTALLATION.md)
- [Build and package guide](docs/BUILD.md) · [Español](docs/es/BUILD.md)
- [Verification and limits](docs/VERIFICATION.md) · [Español](docs/es/VERIFICATION.md)
- [Release notes](docs/RELEASE.md) · [Español](docs/es/RELEASE.md)
- [`installer/`](installer): selection, checks, transactions and Decky adapter.
- [`components/`](components): application sources, installers and resources.

Original code is MIT-licensed, **not every bundled item**. RyzenAdj and third-party assets keep their licenses; owner-supplied PNG icons are not relicensed as MIT. See [THIRD-PARTY.md](THIRD-PARTY.md).

POWER/RGB remain **1.2** with their documented recovery features. The new individual package and central suite contain the same native video ZIP; the six previous individual packages retain their bytes. Releases **v1.2 and v1.0.0** remain intact. Video Output ALLY for DOCKs is a BSD-3-Clause derivative with original credits. Loading/automated checks are not physical validation of every monitor/dock in Gaming.
