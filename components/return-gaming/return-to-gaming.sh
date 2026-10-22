#!/usr/bin/env bash
set -u
if ! command -v kdialog >/dev/null || ! command -v steamosctl >/dev/null; then
    printf '%s\n' 'Se necesitan kdialog y steamosctl. No se cambia de sesión.' >&2
    exit 1
fi
kdialog --title 'Volver al modo Gaming' --yesno '¿Seguro que quieres cerrar el escritorio y volver al modo Gaming? Guarda primero tu trabajo.' || exit 0
mode="$(steamosctl get-default-login-mode 2>/dev/null)" || exit 1
case "$mode" in
    desktop) steamosctl switch-to-game-mode ;;
    game)
        if command -v qdbus6 >/dev/null; then
            qdbus6 org.kde.Shutdown /Shutdown org.kde.Shutdown.logout
        elif command -v qdbus >/dev/null; then
            qdbus org.kde.Shutdown /Shutdown org.kde.Shutdown.logout
        else
            kdialog --error 'No se ha encontrado qdbus6/qdbus. No se cierra la sesión.'
            exit 1
        fi ;;
    *) kdialog --error 'SteamOS no devuelve un modo de arranque reconocido. No se cierra la sesión.'; exit 1 ;;
esac
