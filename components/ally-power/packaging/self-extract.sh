#!/bin/bash
set -euo pipefail
# Ally Power offline installer. Generated payload has an integrity checksum.
if [[ "${1:-}" == --help ]]; then
    printf '%s\n' 'Ally Power 1.0.0 · SteamOS x86_64' 'Sin opciones: instalar' '--check: comprobar sin instalar' '--extract CARPETA: extraer sin instalar' '--uninstall: desinstalar'
    exit 0
fi
ally_archive=$(readlink -f -- "$0")
ally_temp=$(mktemp -d /tmp/ally-power-installer.XXXXXXXX)
cleanup() {
    case "$ally_temp" in /tmp/ally-power-installer.*) rm -rf -- "$ally_temp" ;; esac
}
trap cleanup EXIT
tail -n +@PAYLOAD_LINE@ "$ally_archive" > "$ally_temp/payload.tar.gz"
printf '%s  %s\n' '@PAYLOAD_SHA256@' "$ally_temp/payload.tar.gz" | sha256sum --check --status || {
    printf '%s\n' 'ERROR: instalador incompleto o dañado.' >&2
    exit 1
}
if [[ "${1:-}" == --extract ]]; then
    [[ $# == 2 && ! -e "$2" ]] || { printf '%s\n' 'Indica una carpeta nueva que no exista.' >&2; exit 1; }
    mkdir -p -- "$2"
    tar -xzf "$ally_temp/payload.tar.gz" --no-same-owner -C "$2"
    printf 'Extraído en: %s\n' "$2"
    exit 0
fi
tar -xzf "$ally_temp/payload.tar.gz" --no-same-owner -C "$ally_temp"
/usr/bin/python3 "$ally_temp/Ally-Power-1.0.0/installer.py" "$@"
exit $?
__ALLY_POWER_PAYLOAD__
