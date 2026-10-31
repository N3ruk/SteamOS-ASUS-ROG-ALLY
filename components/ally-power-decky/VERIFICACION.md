# Verificación

## Recuperación optativa 1.2 — validada (31/10/2026)

- El usuario confirmó funcional la preparación CPU previa y posteriormente la
  nueva recuperación automática tras despertar en Gaming. No indicó número de
  ciclos para esta última validación ni se extrapola a otras Ally.
- 115 pruebas Python y 16 JavaScript aprobadas, TypeScript/Rollup correctos.
  Carga real frontend/backend 1.2, opción activada y persistencia tras recarga
  comprobadas. Los probes nativos verificaron scope y liberación del inhibidor,
  sin cambiar CPU/TDP ni forzar una suspensión para probar.
- Snapshot solo en memoria; opción persistida sin perfiles/arranque automático.
  Cuenta atrás 10s de pulsos, reinicio con hueco>4s, plazo60s, cancelación manual/
  sesión/juego/gestores y verificación CPU aún igual a la preparación.
- Recuperación serial TDP primero, CPU al final. Nueva lectura nativa entre
  etapas y nuevo inhibidor antes de reducir CPU. Cada etapa se consume una vez.
- Watch logind para TDP sin inhibidor ni CPU/HID; se reconoce incluso el aviso
  sin FD para no dejar una espera del ciclo anterior. EOF de worker por cambio
  de época es esperado y no borra el snapshot.
- Cobertura simulada de CPU/TDP independientes, cargador perdido, cambio de
  perfil nativo, edición durante adquisición, duplicados, fallo de preparación,
  estado transitorio de Steam, tiempo caducado, cold boot sin aplicar y ajustes
  inmutables. TypeScript/Rollup y pruebas Python/JS antes de instalar.



## Candidata 1.2 — suspensión (31/10/2026)

- Kernel nocturno: CPU8–15 offline a01:54:04; CPU7/6/5/4 offline después;
  CPU3 watchdog remoto sin respuesta a01:54:15; entrada s2idle sin retorno
  persistido. Es compatible con fallo SMT/CPU reducida documentado upstream,
  no una demostración única de causalidad. Pérdida de controles sin traza concluyente.
- Auxiliar enrolado en scope user.slice antes de iniciar el controlador.
  Guardas por ciclo de suspensión y freezer en cada frontera de hardware.
- logind delay FD adquirido antes de reducir CPU; preparado CPU completo antes
  de PM, sin TDP ni HID. Rollback/normalización rechazan sesiones caducadas y
  cambios de otro gestor; fallo de comunicación no restaura hardware.
- Pruebas con sysfs/procesos/D-Bus simulados, TypeScript y Rollup. No se prueba
  suspensión ni TDP/SMT sobre el host. La preparación y recuperación
  posteriores fueron validadas en Gaming por el usuario antes de publicar.
- Las secciones siguientes son históricas: las restauraciones ante caída de
  1.1.x no describen el comportamiento de 1.2.


## Versión 1.1.2 — SMT y CPUs offline

- Estado real antes de corregir: SMT off, CPUs online 0–7; el backend declaraba
  incorrectamente max_cores=16. `cpu8..15/topology` ya no existía.
- Eliminado el fallback que convertía cada CPU offline en núcleo físico nuevo.
  Topología completa cacheada e instantánea local root-owned para reinicios offline.
  El fallback de IDs x86 se rechaza si está incompleto/colapsado. Se prueba la
  prioridad de la instantánea ante IDs offline a cero, sin necesitar escritorio.
  Solo se guardan metadatos físicos, ninguna escritura de hardware para detectar.
- 51 pruebas Python y 8 JavaScript. Se añaden hogares sysfs/debugfs temporales
  que retiran los directorios de CPUs offline como el kernel real; arranque con
  SMT apagado, núcleos completos offline, reinicio del controlador, rechazo de
  datos incompletos y 240 configuraciones CPU en diez ciclos simulados.
- TypeScript y Rollup correctos. Pruebas CPU/TDP solo simuladas; la repetición
  física desde Gaming queda para la prueba del usuario.

## Versión 1.1.1 — Gaming e interfaz reducida (2026-10-23)

- Causa del bloqueo identificada: `in_gaming` solo aceptaba `gamescope`, pero los
  registros de este host identifican el proceso principal como `gamescope-wl`.
  La detección se comparte entre interfaz, adquisición, monitor y puerta de escritura.
- Se aceptan ambos nombres exactos; no se aceptan los procesos auxiliares.
- 37 pruebas Python y 8 JavaScript superadas, más TypeScript estricto y Rollup.
  Regresiones: detección del compositor renombrado, monitor sin cesión errónea y
  transacciones CPU/TDP permitidas con hardware simulado.
- Interfaz reducida a un único recuadro de estado y Ajuste manual completo.
  Los motivos de bloqueo y errores se muestran dentro del mismo recuadro.
- No se ha cambiado de sesión ni escrito TDP/SMT para estas pruebas. La interacción
  física en Gaming sigue pendiente; el equipo estaba en escritorio.

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
