# Ally Power para Decky — 1.1.0

Control manual de TDP, SMT, núcleos e hilos para SteamOS en ROG Ally RC71L o
Ally X RC72LA con Ryzen Z1/Z1 Extreme. No es un gestor para Steam Deck ni para Z2.

## Qué permite

- 3–25 W con batería, 3–30 W con cargador; ajuste conjunto STAPM/fast/slow.
- Activar/desactivar SMT y elegir núcleos/hilos sin desactivar CPU 0.
- Leer temperatura, batería y CPU; ver el límite TDP configurado.
- Cambios en tiempo real, sin botones Aplicar, Restaurar ni Liberar.
- TDP y CPU independientes: SMT/núcleos/hilos funcionan con el TDP nativo de Steam.

## Instalar

Necesitas Decky Loader. En sus ajustes activa el modo desarrollador y utiliza
**Instalar plugin desde ZIP** para seleccionar `Ally-Power-Decky-1.1.0.zip`.
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

Cerrar el panel no libera el control. Salir de Gaming o descargar el plugin
conserva el estado y cede el control. Al apagar el interruptor se cede solo TDP,
no SMT/CPU. Ante caída/EOF del controlador se intenta restaurar únicamente los
dominios que el plugin controla: nunca restaura TDP si ya lo ha devuelto a Steam.
No restaura encima de un gestor nuevo detectable. Una restauración no puede
asegurarse ante SIGKILL, apagado abrupto o fallos del firmware.

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
node --test tests/test_live_queue.mjs tests/test_steam_tdp.mjs
python3 build.py
```

Usa `@decky/api`, `@decky/ui` y el empaquetador oficial `@decky/rollup`.
Ver `VERIFICACION.md` para las comprobaciones realizadas. Fuentes y licencias de
RyzenAdj están en `licenses/`. El motor deriva de Ally Power (MIT); la copia del
motor incluye el protocolo adicional de cesión sin escritura `yield`.
