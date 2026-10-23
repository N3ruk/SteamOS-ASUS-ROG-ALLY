# Verificación y límites

## Suite 1.0.0

- 42 pruebas de selección, catálogo, integridad, instaladores y adaptadores Decky.
- ALLY RGB: 46 pruebas Python y 12 JavaScript; TypeScript estricto y Rollup correctos.
- 100 pruebas automatizadas de la suite y ALLY RGB en esta verificación. Los números
  se refieren a casos de prueba, no a equipos físicos.

La interfaz gráfica se prueba con todas las casillas desmarcadas. No ofrece Ally Power
Decky ni ALLY RGB cuando Decky está inactivo o faltan los requisitos de cada componente.

Se usan hogares temporales, servicios y dispositivos simulados: instalación sin cambiar
sesión/arranque/hardware, rutas con espacios, archivos y enlaces originales, reinstalación,
desinstalación, rechazo de modificaciones manuales/directorios enlazados, rollback y exclusión.
También manifiestos corruptos/traversal, Decky instalado/activo, solicitud exacta, hashes y
rechazo de confirmaciones de otro plugin. ALLY RGB no se sustituye si controla luces o está
pausado; la copia de versiones conocidas se comprueba sin modificar ajustes.

El adaptador RGB distingue archivos antiguos con la misma versión, verifica el manifiesto
nativo y no reenvía una confirmación si el frontend reconecta. Los errores de transporte
no muestran el token de la conexión. Nada descarga dependencias ni habilita servicios.

## Paquetes

Los siete ZIP se extraen en temporal y se verifican `.run`, SHA256, manifiesto, catálogo,
fuentes, licencias y `--check --json`, sin instalar. Se contrastan los payloads ejecutables
con sus fuentes, incluyendo el ZIP nativo ALLY RGB 1.0.0. Los cinco individuales anteriores
se conservan byte a byte al construir `--only central ally-rgb`. El centralizado contiene
los seis componentes y el individual RGB solo ese componente.

Las fechas y orden de archivos son fijos. Un build selectivo repetido debe dar los mismos
hashes de los siete ZIP y SHA256SUMS. Esto comprueba integridad, no es una firma de autor.

## ALLY RGB

Efectos, velocidades y colores independientes; cambiar la selección no modifica el frame,
no escribe luces y no reinicia fases de otras zonas. Cuatro efectos distintos se componen
en un único trabajador. Grupo mixto conserva ajustes hasta una edición explícita; cambios
pendientes no se pierden al cambiar de selector. Las cuatro configuraciones sobreviven a
reinicio del gestor y suspensión/reanudación simulados. Recuperación desactivada o archivo
corrupto no aplica colores; no se sobreescribe el archivo corrupto.

Backend/frontend cargados y readback de animaciones existentes observados en una RC71L:
las ondas continuaron al seleccionar otra zona. Esto no es una observación visual del color
físico ni un ciclo real de apagado/suspensión. El empaquetado no reinstala el plugin activo.

## Otras aplicaciones y límites

Se conservan los contenidos de Ally Power (escritorio 1.0.0 y plugin nativo 1.1.2) y los
otros individuales. Sus comprobaciones previas incluyeron 31 pruebas de escritorio y
51 Python + 8 JavaScript de Ally Power Decky, sin escrituras reales TDP/SMT. Las instantáneas
de topología se generan en el destino, nunca se empaqueta la del equipo constructor.

La app Bluetooth fue probada manualmente por el usuario. La instalación completa en
un sistema nuevo y otras Ally/Ally X requiere validación física. ALLY RGB solo se ofrece
en RC71L; Ally X no está validada. Ninguna prueba aislada acredita compatibilidad universal
con todas las versiones de SteamOS, Decky o Steam. El TDP nativo usa una API interna.

No se resuelven dependencias modificando el sistema. Si faltan, se explica y el componente
no está disponible. Las pruebas de empaquetado no cambian TDP, SMT, Bluetooth, RGB ni arranque.
