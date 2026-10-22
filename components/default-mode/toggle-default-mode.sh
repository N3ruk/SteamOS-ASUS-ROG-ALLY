#!/usr/bin/env bash
set -u

APP_NAME="SteamOS Default Mode Toggle"

show_info() {
    local message="$1"
    if command -v kdialog >/dev/null 2>&1; then
        kdialog --title "$APP_NAME" --msgbox "$message"
    elif command -v zenity >/dev/null 2>&1; then
        zenity --info --title="$APP_NAME" --text="$message"
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send "$APP_NAME" "$message"
    else
        printf '%s\n' "$message"
    fi
}

show_error() {
    local message="$1"
    if command -v kdialog >/dev/null 2>&1; then
        kdialog --title "$APP_NAME" --error "$message"
    elif command -v zenity >/dev/null 2>&1; then
        zenity --error --title="$APP_NAME" --text="$message"
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send --urgency=critical "$APP_NAME" "$message"
    else
        printf 'ERROR: %s\n' "$message" >&2
    fi
}

if ! command -v steamosctl >/dev/null 2>&1; then
    show_error "No se ha encontrado 'steamosctl'.\n\nEsta utilidad está diseñada para versiones actuales de SteamOS que incluyen steamosctl."
    exit 1
fi

current_mode="$(steamosctl get-default-login-mode 2>/dev/null | tr -d '[:space:]')"

case "$current_mode" in
    game)
        target_mode="desktop"
        target_label="Modo Escritorio"
        ;;
    desktop)
        target_mode="game"
        target_label="Modo Gaming"
        ;;
    *)
        show_error "No se ha podido determinar el modo de arranque actual.\n\nValor recibido: ${current_mode:-<vacío>}"
        exit 1
        ;;
esac

if ! output="$(steamosctl set-default-login-mode "$target_mode" 2>&1)"; then
    show_error "SteamOS no ha podido cambiar el modo de arranque.\n\n${output:-Sin detalles adicionales.}"
    exit 1
fi

verified_mode="$(steamosctl get-default-login-mode 2>/dev/null | tr -d '[:space:]')"

if [[ "$verified_mode" != "$target_mode" ]]; then
    show_error "Se ejecutó el cambio, pero la comprobación posterior no coincide.\n\nEsperado: $target_mode\nDetectado: ${verified_mode:-<vacío>}"
    exit 1
fi

show_info "Ahora el arranque por defecto está configurado en $target_label.\n\nLa sesión actual no cambiará. El nuevo modo se usará en el próximo arranque o inicio de sesión."
