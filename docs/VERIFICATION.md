# Verification and limits

[Español: full recorded history](es/VERIFICATION.md)

## Recorded checks for suite 1.3

| Area | Recorded result |
| --- | --- |
| Suite selection/catalog/integrity/installers/Decky adapters | 64 automated tests |
| ALLY POWER Decky | 115 Python + 16 JavaScript tests; TypeScript/Rollup passed |
| ALLY RGB | 124 Python + 18 JavaScript tests; strict TypeScript/Rollup passed |
| Video Output ALLY for DOCKs | 53 Python + 5 frontend tests; TypeScript/Rollup passed |
| Desktop Power prior checks | 31 tests |

These are test cases, not numbers of physically tested devices. Earlier POWER/RGB checks remain recorded; video integration changes neither their sources nor payloads. GUI checks start with all boxes unchecked and unavailable Decky components hidden when Loader/requirements are absent.

Temporary homes, fake services/devices and mock hardware cover paths with spaces, original files/symlinks, reinstall/uninstall, manual-change rejection, rollback/exclusion, corrupt/traversal manifests, active Decky, exact request/hash/confirmation and read-only reconnection. Installation tests do not change real sessions, boot or hardware. Missing requirements are reported, not installed.

## Packages

All eight ZIPs are extracted in temporary directories and `.run`, SHA256, manifests, catalog, source/licenses and `--check --json` verified without installation. Native payload files are compared with sources, including POWER/RGB 1.2 and video 1.0. `--only central video-output-ally` retains the six previous individuals byte-for-byte; central contains all seven components, each individual only its own.

Fixed dates/order allow repeated selective builds to check byte identity. This is integrity verification, not an author signature. Destination hardware topology is discovered on installation, never shipped from the builder.

## RGB evidence and limits

Independent effects/speeds/colors, editor-only selection, mixed groups, pending edits and simulated sleep/restart persistence are covered. Disabled/corrupt recovery applies no lights and preserves corrupt files. Battery tests distinguish internal BAT0/BATn from peripherals, `scope=Device`, missing/invalid data; no fallback to a controller battery.

Native backend/frontend load on RC71L and metadata/readback of running animations were observed, **not physical color readback**. HID fallback tests cover identity/descriptor, two-command allowlist, disappearance, brightness and no-write status; transport success does not prove emitted colors. The installer discovers HID without writes.

Recovery uses simulated clocks/pulses to verify 10-second continuity, gaps/deadlines, direct single restore without flashing, manual/unload cancellation, failures without retry and new sleep cycles. Fixed profiles leave no resident LED polling. Helper tests cover verified scope, async enrollment before payload, stale frames/report guards, frozen timeouts, inherited lock, EOF/cancellation/idempotence and native EOF handling. An unterminable helper blocks replacement. Native user.slice probe touched no LEDs.

Recorded active reload: 0.1 seconds without SIGKILL; direct restore after 10 seconds. The user confirmed **three Gaming suspend/resume cycles** with an emulator/recovery active and validated zone pairs 2–3/1–4 and RGB/transition/speed percentages. This does not prove a kernel root cause, physical color readback or universal compatibility. Packaging does not reinstall an active plugin or change host preferences.

## Power evidence and limits

POWER Decky 1.2 includes verified I/O scope, session/freezer guards, bounded logind-delay CPU preparation and optional TDP→CPU recovery after continuous pulses. Mock tests cover cancellations, deadlines, ownership, native Steam changes and domain independence. Real frontend/backend load, switch persistence and scope/inhibitor probes were checked without CPU/TDP writes for packaging. The user later separately confirmed preparation and automatic recovery in Gaming; no cycle count was given for recovery. Existing Desktop 1.0.0 package retained.

Bluetooth was manually tested by the user. A full install on a fresh machine and other Ally/Ally X variants still require physical checks. RGB is offered only on RC71L; Ally X is unvalidated. No isolated test certifies every SteamOS/Decky/Steam version, and native Steam TDP uses an internal API.

## Video evidence and limits

Mock coverage includes guards/rollback, EDID identity/cache/PNP labels, ASUS ALLY internal naming, atomic settings preservation, read-only queries, serialized/cancelable UI refresh and busy/error states. Three engine modules were compared with the previous local version without algorithm changes.

The distribution adapter covers full hash/manifest, identity/version, unsafe paths, backups, original/unknown Output Manager refusal, Gaming/owned/busy/disabled states, exact one-time confirmation, read-only reconnect, actual installed bytes and concurrent locks. No display changes test installation.

Native backend/frontend load and no-write RC71L scope probe succeeded; AOC/Acer/ASUS ALLY labels were observed in metadata. This **does not establish physical Gaming monitor selection, late dock/reconnection or universal hardware support**. No suspend/output changes were performed to test packaging. See the retained Spanish record for historical details.
