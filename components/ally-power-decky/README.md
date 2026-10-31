# Ally Power para Decky — 1.2

Control manual de TDP, SMT, núcleos e hilos para SteamOS en ROG Ally RC71L o
Ally X RC72LA con Ryzen Z1/Z1 Extreme. No es un gestor para Steam Deck ni para Z2.

## Recuperación y suspensión en 1.2

Versión 1.2 validada por el usuario en Gaming el 31/10/2026, incluida la
recuperación automática tras suspensión. Instaladores individual y centralizado
incorporan el mismo ZIP nativo y sus fuentes.

- El auxiliar de hardware espera sin tocar CPU/SMU hasta que su PID esté verificado
  en un scope transitorio `ally-power-io-*.scope` bajo `user.slice`. No se instala
  ningún servicio, hook system-sleep ni arranque automático.
- Cada orden queda ligada al ciclo de suspensión; se comprueba el freezer y
  BOOTTIME–MONOTONIC antes de cada escritura CPU y acceso RyzenAdj. Órdenes viejas,
  pérdida de comunicación, EOF y cierre del auxiliar no restauran ajustes.
- Una sesión recién iniciada, reanudada o con una interrupción de pulsos mayor de
  4 s necesita 10 s de pulsos continuos. La cola CPU/TDP se descarta al cambiar de
  sesión. La recuperación tras dormir es optativa, como se detalla abajo.
- **SMT/núcleos reducidos requieren una protección previa a la suspensión.**
  Antes de permitir esa reducción se adquiere un inhibidor logind de tipo
  `delay`, nunca `block`, mediante D-Bus tipado. Solo se mantiene mientras el
  plugin posee una configuración CPU reducida. Si no se puede adquirir, no se
  reduce CPU. TDP solo no lo necesita. El D-Bus tipado vive en un auxiliar
  de Python del sistema sin acceso al módulo CPU/TDP/HID, porque el Python
  integrado de Decky no incluye xml.etree. El FD real nunca sale de ese auxiliar.
- En `PrepareForSleep(true)`, primero se invalidan las órdenes y después, antes
  del freezer/kernel PM, se activan SMT y todos los hilos de la CPU aún poseída.
  Se exige que el estado coincida con nuestra última transacción y no haya otro
  gestor conocido. No se escribe TDP, RGB, HID ni MCU. La preparación está limitada
  a 2,2 s (el auxiliar logind libera su FD como máximo a los 2,5 s) y siempre libera su FD; systemd aplica además su propio máximo.
- Tras reanudar la CPU permanece completa durante la espera. Con la recuperación
  apagada se mantiene así hasta una nueva acción; encendida, recupera una vez los
  ajustes que poseía POWER. No se toman ajustes nativos de Steam como propios.
- Salir de Gaming o descargar POWER normaliza antes la CPU que aún posee, para
  no dejar SMT apagado sin protección; no normaliza encima de otro gestor.
  Los rollbacks de una transacción fallida siguen separados CPU/TDP y protegidos
  por el mismo ciclo/freezer. SIGKILL, firmware colgado o una operación kernel
  que no termine no permiten garantizar la preparación: se registra el fallo,
  sin bucles ni reintentos. No se fuerza una suspensión de prueba.

Referencias: [SMT y suspensión en ROG Ally, SimpleDeckyTDP](https://github.com/aarron-lee/SimpleDeckyTDP#rog-ally-troubleshooting),
[logind PrepareForSleep e inhibidores delay](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.login1.html),
[freezer de user.slice](https://www.freedesktop.org/software/systemd/man/latest/systemd-suspend.service.html).

## Recuperar ajustes al despertar

El interruptor **Recuperar ajustes al despertar** es optativo. Solo guarda en
`resume.json` si la función está habilitada: **no guarda perfiles CPU/TDP en disco
ni los aplica al arrancar/reiniciar/reinstalar el plugin**.

Antes de suspender recuerda en memoria la última configuración CPU confirmada
que todavía posee y, si procede, el objetivo TDP que controlaba POWER. Mantiene
la preparación de seguridad: SMT/todos online antes de PM. Si esa preparación
no se confirma, no vuelve a reducir CPU automáticamente.

Al reanudar espera 10 segundos de pulsos continuos de Steam, en Gaming y con el
juego original identificado. Los huecos >4s reinician la espera; si Steam aún
no reconoce el juego se espera, sin aplicar sus ajustes al menú. El intento
caduca a los 60s y no se reintenta.

La aplicación tiene dos etapas consumidas una sola vez:

1. TDP primero, mientras CPU sigue completa, y solo si el control nativo de Steam
   sigue desactivado y su perfil/valor guardado no cambió. Respeta el techo actual
   batería/cargador; nunca desactiva por su cuenta el TDP nativo para recuperar.
2. Nueva lectura del estado de Steam y después CPU/SMT. Comprueba que la CPU
   siga exactamente como la dejó la preparación y adquiere de nuevo el inhibidor
   de seguridad ANTES de volver a reducirla. Una operación TDP lenta no queda
   por delante de la preparación de una CPU ya reducida.

Se cancela al editar/apagar la opción, suspender otra vez, salir de Gaming,
cambiar de juego o detectar otro gestor/bloqueo. La cesión a Steam descarta TDP;
si ocurre durante la aplicación se cede sin reducir CPU. No se sobrescribe una
CPU que cambió otro gestor. CPU sola no lee/escribe SMU/TDP; TDP solo no cambia
CPU ni adquiere inhibidor: usa observación logind tipada sin FD de retraso.

El recuadro de estado muestra la cuenta atrás y el resultado/cancelación. La
función sigue trabajando con QAM cerrado mediante los pulsos globales del plugin.
Las pruebas de reanudación reales corresponden al usuario: no se fuerza suspensión
ni se cambia TDP/SMT del equipo para verificar el paquete.

## Historial 1.1.2

- Topología física estable al alternar SMT o apagar núcleos/hilos. Linux retira
  `cpuN/topology` de CPUs offline: no se deben contar como núcleos independientes.
- Se conserva la topología completa validada durante la vida del proceso. Para
  arrancar con SMT ya apagado se consultan una instantánea root verificada del propio plugin o escritorio. El fallback
  debugfs solo se admite si los IDs son completos; este kernel puede ponerlos a cero.
- Si el kernel no permite identificar una CPU offline se rechaza esa detección;
  no se inventan núcleos ni se activa SMT para inspeccionarlos.

## Cambios 1.1.1

- Interfaz con un único recuadro de estado y el apartado completo Ajuste manual.
- Corregida la detección de Gaming: reconoce `gamescope-wl`, el nombre real del
  compositor en este SteamOS; antes todos los controles quedaban deshabilitados.
- Los errores se muestran dentro del recuadro de estado, sin paneles adicionales.

## Qué permite

- 3–25 W con batería, 3–30 W con cargador; ajuste conjunto STAPM/fast/slow.
- Activar/desactivar SMT y elegir núcleos/hilos sin desactivar CPU 0.
- Leer temperatura, batería y CPU; ver el límite TDP configurado.
- Cambios en tiempo real, sin botones Aplicar, Restaurar ni Liberar.
- TDP y CPU independientes: SMT/núcleos/hilos funcionan con el TDP nativo de Steam.

## Instalar

Necesitas Decky Loader. En sus ajustes activa el modo desarrollador y utiliza
**Instalar plugin desde ZIP** para seleccionar `Ally-Power-Decky-1.2.zip`.
No necesita OpenClaw, PowerTools, un servicio nuevo ni acceso a Internet al funcionar.
Desinstala desde los ajustes de Decky. El ZIP y las fuentes están disponibles por
separado. El plugin solicita la bandera root de Decky para modificar CPU y TDP.

## Cómo evitar conflictos

1. **Desactiva PowerTools u otro controlador TDP/SMT en los ajustes de Decky**.
   Ocultarlo no lo detiene. No se desactiva ni desinstala nada sin una acción tuya.
2. Cierra la app de escritorio Ally Power con **Cerrar y conservar** antes de
   aplicar desde Gaming. Ambos usan `/run/desktop-power.lock`: solo uno puede
   mantener el control. Se reutiliza el mismo motor, no un servidor compartido.
3. El primer control de **Ajuste manual** es **TDP de Steam desactivado**.
   Apagado: el plugin no escribe TDP; Steam usa su control nativo. Encendido:
   desactiva realmente el ajuste nativo de Steam y habilita el deslizador TDP.
   Al apagarlo se cede TDP antes de volver a activar el ajuste nativo de Steam.
4. SMT, núcleos e hilos funcionan con el interruptor en cualquier posición. Cada
   operación de CPU escribe solo CPU, nunca TDP, ni siquiera al revertir un fallo.
5. Los cambios se aplican automáticamente al mover cada control; las repeticiones
   de los deslizadores se agrupan durante 120 ms y se conserva el último valor.
   No hay botones de aplicar, liberar ni restaurar, ni diálogos de confirmación.

Al cargar el plugin no se aplica nada. No hay perfiles por juego, reaplicación
periódica forzada ni restauración de perfiles al arrancar. Solo se vigila el
techo de batería cuando el plugin tiene activado su control TDP. Con TDP nativo
no se limita ni se restaura TDP desde el plugin, aunque SMT/CPU estén controlados. El monitor local de dos segundos
solo funciona dentro de Decky, no usa IA, Internet ni ninguna suscripción.

Al desaparecer Gamescope o detectarse otro gestor conocido se cede el control
sin restaurar encima de sus ajustes. La detección de Gamescope es por proceso:
una sesión Gamescope anidada en escritorio puede contar como Gaming. El bloqueo
con Ally Power sigue siendo exclusivo incluso en ese caso.

La lista de procesos conocidos NO es una garantía frente a todo programa,
script, firmware o gestor nuevo que escriba directamente en la SMU/sysfs.
El plugin no puede bloquear los cambios internos de Steam/firmware. Si otro
gestor no es detectable, debes desactivar sus controles manualmente.

Cerrar el panel no libera el control. Apagar el interruptor cede solo TDP,
no CPU/SMT. Salir de Gaming/descargar normaliza la CPU reducida aún poseída;
EOF/timeout no ejecutan restauraciones. La preparación de suspensión descrita
arriba es una operación explícita de seguridad previa a PM, no recuperación
periódica ni un perfil automático. No se garantiza con SIGKILL o kernel bloqueado.

### Integración con Steam

Utiliza el mismo setter de ajustes que la interfaz nativa de Steam
(`steamos_tdp_limit_enabled`). Se comprobó que ese setter y el valor booleano
están disponibles en el cliente instalado. Es una API interna de Steam y puede
cambiar con sus actualizaciones. Si no se reconoce, se deshabilita solo la parte
TDP y se mantiene CPU/SMT disponible.

Si Steam reactiva su TDP por un perfil de juego o una acción externa, el plugin
cede TDP en lugar de forzar otra desactivación; SMT y CPU siguen disponibles.
El sondeo local continúa con el panel cerrado y no usa IA ni suscripciones.

## TDP configurado no es consumo medido

SteamOS puede bloquear la lectura de la SMU. En ese caso se muestran los límites
ASUS o el último valor confirmado por RyzenAdj. La interfaz no los presenta como
vatios reales de consumo; otras herramientas pueden dejar esos valores obsoletos.
No se han desactivado protecciones del kernel ni instalado módulos adicionales.

Se prioriza el RyzenAdj ya instalado con la app de escritorio, que fue validado
en este equipo. Si no existe, se utiliza el v0.19.0 incluido. Los comandos de ambos
formatos de confirmación están cubiertos por pruebas; eso no prueba físicamente el
consumo sostenido a 3 W ni la compatibilidad en otra Ally.

## Desarrollo

```sh
npm ci --ignore-scripts
npm run typecheck
npm run build
python3 -m unittest discover -s tests -v
node --test tests/test_live_queue.mjs tests/test_steam_tdp.mjs tests/test_session_frontend.mjs
python3 build.py
```

Usa `@decky/api`, `@decky/ui` y el empaquetador oficial `@decky/rollup`.
Ver `VERIFICACION.md` para las comprobaciones realizadas. Fuentes y licencias de
RyzenAdj están en `licenses/`. El motor deriva de Ally Power (MIT); la copia del
motor incluye el protocolo adicional de cesión sin escritura `yield`.

Los metadatos físicos validados se conservan en `/var/lib/ally-power-decky/cpu-topology.json`,
sin ajustes TDP/SMT. Se generan en cada equipo solo desde sysfs completo. Si faltan
identidades fiables e instantánea válida, se rechaza el control en lugar de adivinar núcleos.
