# ALLY RGB — Decky 1.0.0

Control exclusivo de iluminación para **ASUS ROG Ally RC71L con SteamOS x86_64**.
No modifica TDP, SMT, núcleos/hilos, carga, ventiladores, EC ni MCU. Ally X no está validada.

## Funciones y uso

- Cuatro zonas RGB, todas, por parejas o una a una.
- **Efecto, velocidad, color y transición propios de cada zona**, funcionando simultáneamente.
- Color fijo, respiración, arcoíris, onda, transición y batería interna de la Ally.
- Color manual mediante canales rojo/verde/azul; transición con **Color inicial** y **Color final**.
- Brillo y encendido/apagado generales. El kernel expone un único brillo para los cuatro LED.
- **Recuperar al despertar/encender** guarda automáticamente la configuración completa de las cuatro zonas.

Seleccionar una zona solo cambia lo que editas: no congela ni reinicia las demás.
Puedes combinar respiración azul en una zona, transición en otra y colores fijos en las restantes.
Un grupo con efectos diferentes muestra **Varios efectos (conservar)** hasta que elijas un efecto
para ese grupo. Los cambios se aplican en tiempo real, sin botón Aplicar.

Las zonas se numeran 1–4; no se promete un mapa físico izquierda/derecha no confirmado.
No incluye colores rápidos, perfiles, botones de control adicionales ni sincronización con audio/pantalla.

El porcentaje y el efecto **Batería** leen la batería interna (`BAT0`), no la de los
mandos u otros periféricos. Se admiten baterías internas sin atributo `scope`, pero se
excluye `scope=Device`. Si no hay lectura interna válida aparece «batería sin datos»;
el efecto Batería no se aplica con un porcentaje inventado.

## Instalar

Selecciona **ALLY RGB — Decky** en el centralizado o descarga **ALLY-RGB-1.0.0.zip**,
extrae y ejecuta **ALLY-RGB-1.0.0-SteamOS.run** desde escritorio, sin sudo.
Nada está seleccionado por defecto. Solo se ofrece si Decky está instalado y activo,
existe `python3-aiohttp` y el kernel expone los cuatro colores empaquetados esperados.
El instalador no instala Decky, Python ni controladores adicionales.

El individual es un instalador autónomo, no el ZIP nativo que espera directamente Decky.
Para obtener el ZIP nativo y las fuentes sin instalar:

```bash
bash ALLY-RGB-1.0.0-SteamOS.run --extract fuentes
```

El archivo **fuentes/payloads/ALLY-RGB-1.0.0.zip** sí es el ZIP nativo de Decky,
con carpeta superior `ally-rgb/`. Usa Instalar plugin desde ZIP de Decky si prefieres la vía manual.

La suite verifica SHA256, identidad, versión y manifiesto del ZIP antes de solicitar la
instalación local de Decky. Solo confirma la solicitud exacta y comprueba archivos instalados,
versión registrada y respuesta del backend. Una reconexión no reenvía la confirmación.
No reinicia Steam ni otros plugins. Si el panel conserva la lista anterior, vuelve a abrirlo;
si tu versión de Decky no la actualiza, usa su gestión nativa y reinicia Steam manualmente cuando te convenga.

## Recuperación y convivencia

Abrir el panel y consultar estado no cambia las luces. En una instalación sin ajustes
anteriores no se aplican colores al cargar. Si ya tenías una configuración guardada con
**Recuperar al despertar/encender** activado, el plugin la restaura al cargar Decky,
incluso sin abrir su panel. Conserva estado apagado, brillo y los cuatro efectos/colores/velocidades.
Desactivar la opción impide la restauración automática, pero no borra los ajustes.
Al despertar depende de las notificaciones de Steam; no controla las luces durante la suspensión.

No uses otro escritor RGB a la vez. ALLY RGB detecta HueSync, HHD, Ally Center, asusd
u OpenRGB y rechaza competir; no los detiene ni desinstala automáticamente. Detección por procesos
no garantiza conocer firmware u otros escritores. Ally Power puede controlar potencia de forma
independiente: ALLY RGB no usa su bloqueo ni cambia su configuración.

Cerrar el panel deja las animaciones funcionando. Descargar/desinstalar el backend detiene
su trabajador sin restaurar colores encima de otro gestor. Una modificación externa o desaparición
del dispositivo provoca cesión, sin bucle de reimposición.

## Actualizar o quitar

La suite rechaza sustituir ALLY RGB si controla luces o está pausado con recuperación pendiente.
No basta con salir de Gaming: la recuperación automática puede mantener activo el backend.
En ese caso desactívalo desde Decky y utiliza su instalador nativo para actualizar, sin que la suite
lo detenga por ti. Para una instalación reconocida e inactiva se crea antes una copia ZIP en
`$XDG_STATE_HOME/steamos-ally-suite/ally-rgb/` (por defecto `~/.local/state`).
Si Decky utiliza otra carpeta de plugins, `DECKY_PLUGIN_DIR` indica su carpeta padre.
Los ajustes permanecen en el directorio de configuración que proporciona Decky; la suite no los borra.
Para desinstalar usa Decky → Plugins → ALLY RGB → Desinstalar. No añade desinstalador privilegiado.

## Interfaz del kernel y fuentes

Requiere `/sys/class/leds/ally:rgb:joystick_rings`, cuatro entradas `rgb` en `multi_index`
y `max_brightness=255`. Escribe únicamente `multi_intensity` (cuatro valores RRGGBB) y
`brightness`; no abre HID crudo. Runtime Python stdlib, sin `termios`, pyserial ni controladores de otras marcas.

- [Código y guía del plugin](../components/ally-rgb/README.md).
- [Pruebas del plugin](../components/ally-rgb/VERIFICACION.md).
- [Verificación y límites de la suite](VERIFICATION.md).
- [Licencias y referencias](../components/ally-rgb/THIRD-PARTY.md).

69 pruebas automatizadas (56 Python y 13 JavaScript), compilación TypeScript/Rollup y carga
real del backend/frontend comprobadas. Se observó por readback que los efectos ya activos continúan
al seleccionar otra zona. No equivale a verificar visualmente los colores, un ciclo físico de
suspensión/encendido o una instalación nueva en cualquier modelo de Ally.
