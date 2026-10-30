# ALLY RGB 1.2

Iluminación para **ASUS ROG Ally RC71L con SteamOS**, desde Decky. Solo iluminación:
no controla TDP, SMT, ventiladores, carga ni el MCU. Ally X no está validada en esta versión.

## Funciones

- Cuatro zonas RGB con efectos, colores y velocidades **independientes y simultáneos**.
- El selector cambia únicamente las zonas que editas: todas, parejas **1 y 2**, **3 y 4**, **2 y 3**, **1 y 4**, o una a una; no detiene otras zonas.
- Brillo 0–100%, encendido/apagado; el brillo es común a los cuatro LED porque el kernel expone un único ajuste.
- Color fijo, respiración, arcoíris, onda, transición y color según la batería interna de la Ally.
- El porcentaje y el efecto Batería excluyen mandos, ratones y otros periféricos. Si no se puede leer la interna, se indica «batería sin datos», sin adivinar un porcentaje.
- Color manual con deslizadores R/G/B; sin colores rápidos, perfiles ni botones adicionales.
- Porcentaje visible 0–100 % junto a cada canal RGB, también en ambos colores de Transición. Se conservan los 256 niveles de cada canal; el porcentaje se redondea solo para mostrarlo.
- Velocidad con porcentaje visible: 0 % es el mínimo del efecto y 100 % el máximo. No se modifica la velocidad guardada ni su rango interno 10–100.
- Transición con **Color inicial** y **Color final** independientes y velocidad regulable.
- **Recuperar al despertar/encender** guarda automáticamente la última configuración aplicada,
  incluyendo los cuatro efectos, sus velocidades y colores, brillo y encendido/apagado.
- Cola de cambios serializada y agrupada: al mover rápido un deslizador se conserva el último valor.

## Instalar

En Decky, activa las opciones de desarrollador y selecciona **Instalar plugin desde ZIP**:
`ALLY-RGB-1.2.zip`. El ZIP lleva una sola carpeta superior `ally-rgb/`.
No necesita instalar Python, pyserial, HHD o controladores HID adicionales.

Desactiva cualquier otro gestor RGB antes de usarlo. ALLY RGB no detiene otros plugins:
si detecta HueSync, HHD, Ally Center, asusd u OpenRGB, bloquea nuevas escrituras.
No son garantías universales frente a firmware o escritores desconocidos.

Abrir el panel o consultar estado **no cambia las luces**. Al cargar el backend, solo se
restaura una configuración guardada válida con **Recuperar al despertar/encender** activado.
Sin ajustes guardados, con la opción desactivada o con ajustes corruptos, no escribe luces.
Al desactivar la opción se conserva la configuración para mostrarla en el panel, pero no
se aplica automáticamente al encender ni al despertar. Cambiar controles sí aplica sus valores.

La recuperación se decide en el backend desde pulsos ligeros de Steam, también
con QAM cerrado. Tras un arranque o una suspensión real (diferencia entre
BOOTTIME y MONOTONIC), espera 10 segundos de pulsos continuos antes de restaurar
una sola vez el perfil vigente. Una pausa de más de 4 s reinicia la cuenta;
sin continuidad en 60 s se omite el intento. No usa hora civil ni hooks internos
Steam. No fuerza un apagado/encendido de los LED.

La candidata local `session-scope-v2` elimina el observador logind, el detector
periódico de suspensión y las consultas RGB de los perfiles fijos. El estado del
panel es caché, no una nueva lectura del dispositivo. Los perfiles fijos se
aplican una vez y liberan trabajador/bloqueo. Solo las animaciones necesitan un
trabajador mientras funcionan.

Antes de **cualquier** petición al auxiliar RGB, systemd lo incorpora a un scope
transitorio dentro de `user.slice`, que SteamOS congela durante la suspensión.
No se instala ningún servicio, hook de sueño, inhibidor ni regla de permisos.
Se verifica el cgroup desde ambos procesos; si falla, no se toca el RGB.
Cada operación/informe comprueba el ciclo de suspensión para rechazar comandos
antiguos. El backend consulta logind solo al aplicar, nunca se suscribe a él.
La edición manual, una nueva suspensión o la descarga cancelan lo pendiente.
Un perfil apagado o con brillo cero no se enciende automáticamente.

Las zonas se numeran 1–4 porque su posición física exacta queda pendiente de confirmar.
El selector **Zonas** solo cambia las zonas que vas a editar; no aplica colores ni reinicia
animaciones. Puedes tener respiración azul en la zona 1, transición en la zona 2, arcoíris
en la zona 3 y un color fijo en la zona 4. Editar una no reinicia el tiempo de las demás.
Si seleccionas un grupo con efectos distintos, aparece **Varios efectos (conservar)**;
solo se igualan si eliges explícitamente un efecto para ese grupo. Al mover un canal RGB,
las zonas seleccionadas cambian ese canal y conservan los demás.
En Transición, cada zona guarda sus propios colores inicial/final y velocidad.
El brillo y el interruptor Iluminación siguen siendo generales, como en la versión anterior.

Las configuraciones de desarrollo anteriores se migran automáticamente cuando son válidas.
La configuración de las cuatro zonas se guarda completa para la recuperación.

Cerrar el panel no detiene los efectos. La descarga del backend o la desinstalación sí los
detiene sin restaurar colores sobre otros gestores. Reiniciar su backend restaura solo si
la opción está activada; no se instala ningún servicio de arranque adicional.

## Backend y requisitos

- Interfaz del kernel: `/sys/class/leds/ally:rgb:joystick_rings`.
- Requiere `multi_index` de cuatro entradas `rgb` y `max_brightness=255`.
- `multi_intensity`: **cuatro colores empaquetados RRGGBB**, no tres componentes R/G/B.
- En kernels compatibles, el control de color escribe `multi_intensity` y `brightness`.
- Si `multi_max_intensity` limita los cuatro valores empaquetados a 255 (como Linux 7.2
  en SteamOS 3.9), usa automáticamente un transporte hidraw **exclusivamente RGB**.
  Identifica RC71L, USB ASUS 0b05:1abe, interfaz 02 y el mismo dispositivo del LED;
  verifica descriptor, identidad del descriptor abierto y nodo de carácter. No usa números hidraw fijos.
- El fallback solo permite informes fijos de cuatro colores y brillo LED. No toca TDP,
  ventiladores, botones, modos del mando, firmware ni persistencia del controlador.
  No descarga el driver ni instala módulos, dependencias o reglas de permisos.
- El dimmer HID escala los canales RGB por software, usando el nivel LED máximo cuando
  está encendido. Se conservan cuatro zonas/efectos y el brillo global continuo.
- HID confirma que el transporte aceptó el comando, **no una lectura física del color**.
  El estado lo distingue mediante `backend` y `verification`; los colores son el último
  frame enviado. Los cambios del dispositivo/estado sysfs provocan cesión y se comprueban
  gestores conocidos, pero no se garantiza detectar otro escritor HID desconocido.
  Ante un envío fallido se cierra el descriptor sin fingir rollback ni confirmación.
- Bloqueo `/run/ally-rgb.lock`; última configuración en `settings.json` del directorio de ajustes de Decky.
- Escritura atómica y fsync de ajustes; los perfiles antiguos no se borran ni se aplican.
- Comprobación de valores, readback del driver y rollback parcial mientras sea el mismo dispositivo.
- Detección de cambios externos al escribir, ausencia del dispositivo y cierre sin reimposición continua; sin vigilancia RGB en reposo.
- El readback del driver no prueba el color físico de los LED ni garantiza persistencia tras reiniciar.

La E/S RGB utiliza biblioteca estándar, incluido `fcntl`, en un auxiliar aislado.
La consulta puntual D-Bus usa el busctl de SteamOS; no ejecuta un observador.
El código legado y la dependencia vendorizada se conservan sin activarse. No instala paquetes, importa `termios`/pyserial ni bibliotecas
HID externas, ni realiza conexiones de red. No sincroniza pantalla/audio.

## Construir y verificar

```bash
npm ci
npm run typecheck
npm run build
python3 -m unittest discover -s tests -v
node --test tests/test_queue.mjs tests/test_ui.mjs
python3 build.py
(cd release && sha256sum -c SHA256SUMS)
```

El ZIP incluye backend, bundle, fuentes de interfaz y pruebas, sin `node_modules`,
credenciales, backups ni datos del equipo. Fechas/permisos del ZIP son fijos.
Las pruebas usan hogares y dispositivos temporales, nunca luces/TDP/SMT reales.

## Licencia y referencias

Código de este plugin bajo MIT. Ver LICENSE y THIRD-PARTY.md. Los protocolos y las
fuentes abiertas se acreditan sin atribuirse la autoría de los proyectos de referencia.

## Arquitectura de recuperación 1.2

`session-scope-v2` sustituye el mecanismo anterior, que no resolvió los bloqueos
observados en Gaming. No se atribuye una causa de kernel demostrada: el registro
fallido termina al entrar en s2idle, sin tramo de reanudación. La asociación con
la función procede de la prueba A/B del usuario.

La E/S real usa `/usr/bin/python3 -I`, protocolo cerrado y flock heredado.
Los auxiliares no reciben comandos antes de verificar su scope. Tras un timeout
se intenta cerrar de forma acotada; si el auxiliar no termina, conserva el
bloqueo y no se crea otro encima. Durante el congelado no se mata el auxiliar ni
se interpreta una pausa del sistema como timeout. Ningún timeout puede resolver
por sí mismo una llamada de kernel no interrumpible.

La aceptación HID confirma el transporte, no el color físico. El estado mostrado
es la última aplicación conocida; un cambio externo en reposo puede no reflejarse
hasta una nueva operación. No hay sondeo para imponer el perfil periódicamente.

Se han validado tres suspensiones/reanudaciones correctas en Gaming con un emulador
en ejecución y la recuperación activada. No se presenta como prueba universal de
compatibilidad ni como demostración de una causa concreta de kernel.

También se han validado las nuevas parejas 2–3 y 1–4 y los porcentajes de color,
transición y velocidad en la interfaz. El centralizado y el instalador individual
incluyen este mismo plugin nativo, manteniendo la versión y el release v1.2.

Referencias del diseño:
- [systemd-suspend: congelación de user.slice](https://www.freedesktop.org/software/systemd/man/latest/systemd-suspend.service.html)
- [Scopes transitorios](https://www.freedesktop.org/software/systemd/man/latest/systemd.scope.html)
- [StartTransientUnit](https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.systemd1.html)
- [SteamOS #2722: bloqueos s2idle en RC71L](https://github.com/ValveSoftware/SteamOS/issues/2722)

### Corrección local de cierre 1.2

La prueba real de recarga con recuperación activa reprodujo el SIGKILL de 5 s,
no detectado por los tests del coordinador. Se corresponde con la incidencia
[Decky #975](https://github.com/SteamDeckHomebrew/decky-loader/issues/975): al
cerrarse IPC, el lector puede girar en EOF sin ceder el bucle y bloquear _unload.
`loader_compat.py` reconoce esa implementación y estaciona únicamente el lector
agotado dentro del proceso de ALLY RGB. No parchea archivos de Decky, POWER ni
servicios; no sustituye una implementación con comprobación EOF nativa. Referencia
adicional: https://github.com/bassobr/decky-ally-dsp/blob/main/py_modules/allydsp/deckyfix.py.
Esto corrige un defecto de cierre observado, no prueba la causa de la suspensión.
