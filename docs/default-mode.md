# Alternar arranque de SteamOS — 1.0.0

Instala «Alternar arranque de SteamOS» y su icono. Cada ejecución alterna el modo predeterminado: **Gaming → Escritorio** o **Escritorio → Gaming**. Lee el estado, ejecuta `steamosctl set-default-login-mode` y verifica el resultado. Informa del modo elegido.

No cambia la sesión actual ni reinicia el equipo. **Instalarlo no altera el arranque**: solo lo hace al abrir el lanzador. No añade una confirmación antes de alternar, conservando el comportamiento de la utilidad original; el cambio se anuncia al terminar.

## Instalar / quitar

Individual: `Alternar-Arranque-SteamOS-1.0.0.zip`. Requiere SteamOS con `steamosctl` y `kdialog`; sin sudo. Aparece en el menú de KDE.

«Desinstalar Alternar arranque de SteamOS» restaura los ficheros originales. No cambia el modo de arranque que ya habías elegido. Para recuperarlo, abre la utilidad una vez más antes de desinstalar si quieres alternarlo de nuevo.

## Fuente

- [`toggle-default-mode.sh`](../components/default-mode/toggle-default-mode.sh).
- [`launchers.py`](../installer/launchers.py): genera `Exec` desde el usuario destino, sin `/home/deck` fijo.
- [`steamos-default-mode-toggle.png`](../components/default-mode/steamos-default-mode-toggle.png): icono aportado, no relicenciado como MIT.

Si `steamosctl` no existe o devuelve un modo desconocido, se muestra el error y no se intenta adivinar el modo. Una actualización de SteamOS puede cambiar esa herramienta; no se sustituyen servicios del sistema para evitarlo.
