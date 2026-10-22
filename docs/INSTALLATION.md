# Instalación, actualización y recuperación

## Instalación normal

Descarga el centralizado o el individual. Extrae el ZIP, permite ejecución del `.run` y ejecútalo sin sudo desde escritorio. No necesitas clonar el repositorio ni instalar dependencias desde internet.

La ventana GTK4 contiene explicaciones y casillas. Si GTK4 no está disponible se usa KDialog; desde terminal sin sesión gráfica existe selección textual. Las dependencias ausentes se muestran: no se usa `pip`, `pacman` ni se modifica SteamOS para resolverlas automáticamente.

El instalador mantiene la ventana ocupada durante cada operación y deja un resultado por componente. Si uno falla, los demás seleccionados se siguen intentando: no hay una transacción global que desinstale aplicaciones correctamente instaladas. Cancela en el diálogo propio de una app si no quieres continuar con ella; ese instalador original puede finalizar con código 0 al cancelar y el resultado lo indica expresamente.

## Archivos y permisos

- Lanzadores: `$XDG_DATA_HOME/applications` y `$XDG_DATA_HOME/steamos-ally-suite/<componente>`; iconos en `icons/hicolor`. Por defecto `~/.local/share`.
- Volver a Gaming añade/reemplaza también `Return.desktop` en el escritorio resuelto por `xdg-user-dir DESKTOP`.
- Sus copias originales y recibos: `$XDG_STATE_HOME/steamos-ally-suite/<componente>/receipt.json`, por defecto `~/.local/state`. El recibo contiene datos originales y nuevos, no solo nombres.
- Ally Power escritorio: `/usr/local/lib/desktop-power`, comandos `/usr/local/bin`, accesos de usuario. Su instalador original conserva backups y restaura el modo de solo lectura de SteamOS si lo desactiva temporalmente.
- Bluetooth: `~/.local/share/bluetooth-trust-manager` y accesos de usuario; respeta `XDG_DATA_HOME`.
- Decky: instalación delegada a Loader, en su carpeta de plugins. No se reinicia Steam, Bluetooth ni otros plugins.

Los lanzadores se sustituyen atómicamente por archivo y se revierten ante excepciones del proceso. **No** es una transacción resistente a corte de corriente entre archivos. No se siguen directorios simbólicos; si una ruta padre es un enlace se rechaza la operación. El enlace final del lanzador sí se respalda y restaura correctamente.

## Actualizar

Vuelve a ejecutar el paquete deseado. Los lanzadores mantienen la copia original de la primera instalación; si cambiaste archivos gestionados manualmente, no se sobrescriben y se pide resolverlo antes. Si cambiaste las rutas XDG o de escritorio, desinstala antes con las rutas originales.

Cierra Ally Power (incluida la bandeja) antes de actualizarlo; cierra Confianza Bluetooth antes de sustituirla. No se cierran por ti.

Decky: sal de Gaming para que el plugin deje de controlar hardware. Se comprueba `get_state.active` y se guarda una copia ZIP antes de sustituir una versión reconocida (1.0.0/1.1.0). Si no se localiza la carpeta o no se puede leer, no se actualiza. Para rutas no estándar, define `DECKY_PLUGIN_DIR` como carpeta padre de `ally-power-decky`. La integración automática se comprobó contra la API local de Decky **3.3.0**; si cambia, el adaptador falla con un mensaje, no fuerza un reinicio ni copia archivos como root. La conexión WebSocket puede reemplazar brevemente la conexión de su frontend, que vuelve a conectarse.

## Desinstalar

- **Lanzadores:** busca «Desinstalar Return to Gaming Mode» o «Desinstalar Alternar arranque de SteamOS» en el menú. Devuelve los archivos originales, o retira los añadidos si antes no existían. Guarda recibo recuperable `removed-*.json`. Si se detectan cambios manuales, no se toca nada. La carpeta vacía y `operation.lock` pueden quedarse; no son procesos.
- **Ally Power:** usa su desinstalador del menú o el `.run` original incluido con `--uninstall`.
- **Bluetooth:** desinstalador del menú o `.run` original con `--uninstall`.
- **Decky:** ajustes de Decky → Plugins → Ally Power → desinstalar. No añade un segundo gestor de desinstalación privilegiada.

Desinstalar el lanzador de arranque **no cambia** el modo predeterminado ya elegido. Desinstalar el lanzador Gaming no cambia la sesión actual. Si una actualización del sistema sustituye iconos o ficheros gestionados, revísalos antes de restaurar; nunca se sobrescriben a ciegas.

## Convivencia de gestores

Puedes tener instaladas las variantes escritorio y Decky, pero no utilizarlas simultáneamente sobre el hardware. Cierra la app de escritorio antes de tomar control en Gaming. Los gestores detectables provocan rechazo; no son desinstalados, desactivados ni detenidos por la suite. La instalación no toma control de TDP ni SMT.
