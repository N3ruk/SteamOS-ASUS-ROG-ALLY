# Verificación

## Versión 1.1.0 — cambios en tiempo real

- 35 pruebas Python y 8 pruebas JavaScript superadas (43 en total).
- Verificado con simulación: CPU/SMT sin control TDP; CPU no invoca RyzenAdj;
  TDP no escribe CPU; cesión a Steam sin clamp ni restauración TDP posterior;
  rollback limitado a cada dominio; cambios rápidos serializados y último valor
  conservado; cesión elimina cambios TDP pendientes sin eliminar cambios CPU.
- Puente Steam probado con setter/estado simulados: activar/desactivar, no escribir
  un valor ya igual y degradación explícita cuando la API no está disponible.
- Mediante inspección de solo lectura del cliente Steam real se reconocen el
  setter usado por Steam y el ajuste booleano `steamos_tdp_limit_enabled`.
  No se ha alternado realmente ni cambiado TDP/SMT para probar esta versión.
- TypeScript estricto y compilación Rollup correctos. Interacción física en Gaming
  todavía pendiente. Los apartados 1.0.x siguientes son el registro histórico.

## Cambio 1.0.1

Retirados el botón «Restaurar estado inicial» y su método público de Decky por
petición del usuario. Conserva «Liberar control y conservar» y la protección
interna de restauración ante caída del controlador; no son la misma función.

## Comprobado en desarrollo

- TypeScript: comprobación estricta y compilación con las bibliotecas de Decky.
- 25 pruebas Python: límites AC/batería, selección CPU/SMT, CPU 0, rollback,
  confirmaciones RyzenAdj v0.14/v0.19, cierre conservando y caída restaurando,
  exclusión por bloqueo compartido con la app, gestores detectables, cambio de
  modo, cesión sin escribir, validación de parámetros y estado de solo lectura.
- Todas las escrituras a TDP y CPU de las pruebas se simulan. No se han aplicado
  cambios de potencia o SMT para probar el plugin.

## Instalación real en este equipo

- Decky Loader v3.3.0 registra Ally Power 1.0.0, API v1, habilitado.
- Instalado con la API de instalación local de Decky, sin reiniciar Steam ni
  otros plugins. Archivos del plugin propiedad de root, binario con modo 0755.
- La llamada real `get_state` reconoce ROG Ally RC71L Z1 Extreme, ocho núcleos y
  dieciséis hilos; detecta PowerTools y el bloqueo de la app de escritorio.
- Se mantiene inactivo, sin controlador de escritura iniciado.
- El bundle de frontend se sirve por Decky con HTTP 200 mediante autenticación.
- No se ha apagado PowerTools ni cerrado la app de escritorio.

## Alcance

Compilar y pasar pruebas no demuestra la interacción del panel dentro de Gaming
ni una modificación física de TDP/SMT desde Decky. Esas pruebas requieren usarlo
en Gaming con PowerTools y el límite TDP de Steam desactivados, y sin la app de
escritorio controlando la CPU. No se ha probado en otra Ally.
