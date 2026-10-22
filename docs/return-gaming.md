# Volver al modo Gaming — 1.0.0

Sustituye para el usuario el lanzador `Return.desktop` y el icono `GAMEMODE` por los recursos personalizados, tanto en el menú como en el escritorio. No modifica el paquete del sistema.

Al abrirlo pregunta **«¿Seguro que quieres cerrar el escritorio y volver al modo Gaming?»**. Cancelar no llama a SteamOS ni cierra nada. Guarda el trabajo antes de aceptar. Si el arranque predeterminado es escritorio usa `steamosctl switch-to-game-mode`; si es Gaming solicita logout mediante KDE, preservando el modo predeterminado. Un valor desconocido o un fallo detienen la acción.

## Instalar / quitar

Paquete individual: `Volver-al-Modo-Gaming-1.0.0.zip`. Ejecuta el `.run` sin sudo y marca el componente. Se requieren `kdialog`, `steamosctl` y `qdbus6` o `qdbus`.

Desinstala desde «Desinstalar Return to Gaming Mode» en el menú. Se restaura el lanzador/icono original, incluido un enlace simbólico de escritorio si existía. Los originales se guardan en el recibo descrito en [Instalación](INSTALLATION.md). No se ejecuta la vuelta a Gaming durante instalación o desinstalación.

## Fuente

- [`return-to-gaming.sh`](../components/return-gaming/return-to-gaming.sh): confirmación y cambio de sesión.
- [`launchers.py`](../installer/launchers.py): genera `.desktop` con las rutas reales del usuario y gestiona backups.
- Icono: [`GAMEMODE.png`](../components/return-gaming/GAMEMODE.png), aportado por el usuario; no relicenciado como MIT.

El icono se llama igual que el original para que el override de usuario tenga prioridad. Si KDE mantiene el antiguo, ejecuta `kbuildsycoca6 --noincremental` en tu sesión normal; no hace falta reiniciar Bluetooth o el sistema.
