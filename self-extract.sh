#!/bin/sh
# Offline self-extracting installer, payload checksum verified before extraction.
set -eu
case "${1:-}" in
    --help|-h) printf '%s\n' 'Instalador SteamOS ASUS ROG ALLY' 'Ejecutar sin sudo. --check comprueba requisitos; --verify comprueba integridad.' '--extract CARPETA_NUEVA extrae sin instalar.'; exit 0 ;;
esac
work=$(mktemp -d "${TMPDIR:-/tmp}/steamos-ally-XXXXXXXX")
trap 'rm -rf -- "$work"' EXIT HUP INT TERM
if ! tail -n +@PAYLOAD_LINE@ "$0" > "$work/payload.tar.gz"; then exit 1; fi
actual=$(sha256sum "$work/payload.tar.gz")
actual=${actual%% *}
if [ "$actual" != '@PAYLOAD_SHA256@' ]; then
    printf '%s\n' 'ERROR: El archivo está incompleto o su integridad no es correcta.' >&2
    command -v kdialog >/dev/null 2>&1 && kdialog --error 'El instalador está incompleto o dañado. Vuelve a descargarlo.'
    exit 1
fi
tar -xzf "$work/payload.tar.gz" -C "$work"
if [ "${1:-}" = '--extract' ]; then
    [ "$#" = 2 ] || { printf '%s\n' 'Uso: --extract CARPETA_NUEVA' >&2; exit 1; }
    [ ! -e "$2" ] && [ ! -L "$2" ] || { printf '%s\n' 'La carpeta de destino ya existe.' >&2; exit 1; }
    mkdir -p -- "$2"
    cp -a -- "$work/@FOLDER@/." "$2/"
    exit 0
fi
python3 "$work/@FOLDER@/install.py" "$@"
exit $?
__ALLY_SUITE_ARCHIVE__
