# ALLY RGB 1.0.0

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
`ALLY-RGB-1.0.0.zip`. El ZIP lleva una sola carpeta superior `ally-rgb/`.
No necesita instalar Python, pyserial, HHD o controladores HID adicionales.

Desactiva cualquier otro gestor RGB antes de usarlo. ALLY RGB no detiene otros plugins:
si detecta HueSync, HHD, Ally Center, asusd u OpenRGB, bloquea nuevas escrituras.
No son garantías universales frente a firmware o escritores desconocidos.

Abrir el panel o consultar estado **no cambia las luces**. Al cargar el backend, solo se
restaura una configuración guardada válida con **Recuperar al despertar/encender** activado.
Sin ajustes guardados, con la opción desactivada o con ajustes corruptos, no escribe luces.
Al desactivar la opción se conserva la configuración para mostrarla en el panel, pero no
se aplica automáticamente al encender ni al despertar. Cambiar controles sí aplica sus valores.

La recuperación al encender funciona cuando Decky carga el plugin, incluso sin abrir su panel.
Puede reintentar hasta 30 segundos si el dispositivo RGB todavía no está disponible.
No reintenta contra otro gestor, un trigger del kernel o después de un cambio manual.
La recuperación al despertar requiere las notificaciones de suspensión/reanudación de Steam.
No controla las luces durante la suspensión y no cambia `sleep_animation` desde la interfaz.

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

El runtime usa únicamente biblioteca estándar compatible con Decky, incluido `fcntl`
para el fallback RGB. No importa `termios`, `serial`, bibliotecas HID externas ni
controladores de otras marcas. No accede a red.
Sin sincronización de pantalla/audio en esta primera versión.

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
