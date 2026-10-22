#!/bin/bash
set -euo pipefail
if [[ "${1:-}" == --help ]]; then
    printf '%s\n' 'Confianza Bluetooth 1.0.0 · SteamOS' 'Sin opciones: instalar para el usuario' '--check: comprobar sin instalar' '--extract CARPETA: extraer en carpeta nueva' '--uninstall: desinstalar sin sudo'
    exit 0
fi
trust_archive=$(readlink -f -- "$0")
trust_temp=$(mktemp -d /tmp/confianza-installer.XXXXXXXX)
cleanup() {
    case "$trust_temp" in /tmp/confianza-installer.*) rm -rf -- "$trust_temp" ;; esac
}
trap cleanup EXIT
tail -n +@LINE@ "$trust_archive" > "$trust_temp/payload.tar.gz"
printf '%s  %s\n' '@HASH@' "$trust_temp/payload.tar.gz" | sha256sum --check --status || {
    printf '%s\n' 'ERROR: instalador dañado o incompleto.' >&2
    exit 1
}
if [[ "${1:-}" == --extract ]]; then
    [[ $# == 2 && ! -e "$2" ]] || { printf '%s\n' 'Indica una carpeta nueva.' >&2; exit 1; }
    mkdir -p -- "$2"
    tar -xzf "$trust_temp/payload.tar.gz" --no-same-owner -C "$2"
    printf 'Extraído en: %s\n' "$2"
    exit 0
fi
tar -xzf "$trust_temp/payload.tar.gz" --no-same-owner -C "$trust_temp"
/usr/bin/python3 "$trust_temp/Confianza-Bluetooth-1.0.0/installer.py" "$@"
exit $?
__CONFIANZA_BLUETOOTH_PAYLOAD__
