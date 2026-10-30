# ALLY RGB 1.2

Iluminación para **ASUS ROG Ally RC71L con SteamOS**, desde Decky. Solo iluminación:
no controla TDP, SMT, ventiladores, carga ni el MCU. Ally X no está validada en esta versión.

## Funciones

- Cuatro zonas RGB con efectos, colores y velocidades **independientes y simultáneos**.
- El selector cambia únicamente las zonas que editas: todas, parejas o una a una; no detiene otras zonas.
- Brillo 0–100%, encendido/apagado; el brillo es común a los cuatro LED porque el kernel expone un único ajuste.
- Color fijo, respiración, arcoíris, onda, transición y color según la batería interna de la Ally.
- El porcentaje y el efecto Batería excluyen mandos, ratones y otros periféricos. Si no se puede leer la interna, se indica «batería sin datos», sin adivinar un porcentaje.
- Color manual con deslizadores R/G/B; sin colores rápidos, perfiles ni botones adicionales.
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

La recuperación se ejecuta en el backend, sin depender de los avisos internos de
suspensión de Steam ni de abrir QAM. Antes de actuar, espera a logind despierto y
sin apagado, a una confirmación ligera de Steam y a una identidad RGB estable 2 s.
Después cuenta 10 s despierto, baja el brillo a cero durante 250 ms y restaura el
perfil vigente una vez. No reinicia USB ni guarda el apagado temporal.
Si no confirma preparación en 60 s, o falla un comando, omite ese ciclo sin
reintentar escrituras. Una nueva suspensión, cambio de identidad, edición manual
o descarga cancela lo pendiente. Un perfil apagado o con brillo cero no se enciende.
La observación usa D-Bus tipado y BOOTTIME/MONOTONIC; la hora civil no interviene.
No consulta ni escribe HID desde el aviso previo a suspensión. No añade servicios,
inhibidores ni hooks del sistema. El control manual conserva un observador de
seguridad mientras está activo aunque la recuperación automática esté desactivada.

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
- Detección de cambios externos, ausencia del dispositivo y cierre sin reimposición continua.
- El readback del driver no prueba el color físico de los LED ni garantiza persistencia tras reiniciar.

La E/S RGB utiliza biblioteca estándar, incluido `fcntl`, en un auxiliar aislado.
La observación D-Bus emplea dbus-next 0.2.3 (MIT), vendorizado, fuera del Python
congelado de Decky. No instala paquetes, importa `termios`/pyserial ni bibliotecas
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

## Recuperación diferida 1.2 (2026-10-30)

La recuperación de arranque y reanudación espera a logind, a una confirmación
ligera de Steam (también con QAM cerrado) y a una identidad RGB estable 2 s.
Después cuenta 10 s despierto y baja el brillo a cero durante 250 ms antes de
restaurar una vez el perfil vigente. No reinicia USB ni guarda el apagado temporal.
Si no confirma preparación en 60 s, o falla un comando, omite ese ciclo sin
reintentar escrituras. Un perfil apagado o con brillo cero no se enciende.

Una nueva suspensión, desconexión, cambio de identidad, edición manual o descarga
cancela lo pendiente. El aviso previo a suspensión únicamente invalida tareas y
solicita terminar el auxiliar: no consulta ni escribe HID ni espera procesos. No
hay inhibidores, hooks instalados en el sistema ni servicios adicionales.

Todo acceso real RGB se realiza en `/usr/bin/python3 -I` mediante un auxiliar de
protocolo fijo; cada RPC tiene timeout y el cierre espera como máximo 150 ms por
auxiliar. La lectura sin control usa un auxiliar que rechaza escrituras. El
auxiliar escritor hereda el flock: si el kernel lo deja bloqueado, conserva el
bloqueo y no se crean sustitutos. Un timeout no puede garantizar interrumpir una
llamada no interrumpible del kernel. Si falla después del apagado temporal, los
LED pueden quedar apagados hasta una intervención posterior.

Para efectos estáticos los auxiliares de hardware son cortos. Para animaciones
se reutiliza un único auxiliar mientras hay actividad para evitar lanzar veinte
procesos por segundo. Cerrar QAM no detiene los efectos. Desactivar recuperación
sin control activo detiene sus observadores; durante control manual activo se
conserva solo la observación necesaria para detener ese control antes de dormir,
sin autorizar ninguna restauración al despertar.

La suscripción tipada logind utiliza dbus-next 0.2.3 (MIT), incluida en `vendor/`,
y funciona fuera del Python congelado de Decky. No instala paquetes de sistema.
El detector BOOTTIME/MONOTONIC invalida/deduplica una reanudación perdida, pero no
inventa que logind o Steam estén preparados. La confirmación de Steam no usa sus
hooks internos de suspensión ni depende de abrir el panel.

La aceptación HID confirma el transporte, no el color físico. Este diseño no
identifica por sí solo la causa de bloqueos previos y requiere pruebas reales de
suspensión/reanudación después de las pruebas simuladas.

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
