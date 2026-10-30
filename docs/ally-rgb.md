# ALLY RGB — Decky 1.2

Control exclusivo de iluminación para **ASUS ROG Ally RC71L con SteamOS x86_64**.
No modifica TDP, SMT, núcleos/hilos, carga, ventiladores, EC ni MCU. Ally X no está validada.

## Funciones y uso

- Cuatro zonas RGB, todas, parejas **1 y 2**, **3 y 4**, **2 y 3**, **1 y 4**, o una a una.
- **Efecto, velocidad, color y transición propios de cada zona**, funcionando simultáneamente.
- Color fijo, respiración, arcoíris, onda, transición y batería interna de la Ally.
- Color manual mediante canales rojo/verde/azul; transición con **Color inicial** y **Color final**.
- Porcentajes visibles 0–100 % de cada canal, incluidos ambos colores de Transición, sin perder los 256 niveles RGB.
- Velocidad indicada de 0 % (mínimo del efecto) a 100 % (máximo), sin cambiar valores guardados ni ritmos anteriores.
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

Selecciona **ALLY RGB — Decky** en el centralizado o descarga **ALLY-RGB-1.2.zip**,
extrae y ejecuta **ALLY-RGB-1.2-SteamOS.run** desde escritorio, sin sudo.
Nada está seleccionado por defecto. Solo se ofrece si Decky está instalado y activo,
existe `python3-aiohttp` y el kernel expone los cuatro colores empaquetados esperados.
El instalador no instala Decky, Python ni controladores adicionales.

El individual es un instalador autónomo, no el ZIP nativo que espera directamente Decky.
Para obtener el ZIP nativo y las fuentes sin instalar:

```bash
bash ALLY-RGB-1.2-SteamOS.run --extract fuentes
```

El archivo **fuentes/payloads/ALLY-RGB-1.2.zip** sí es el ZIP nativo de Decky,
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
La recuperación se decide en el backend desde pulsos ligeros de Steam, también
con QAM cerrado. Detecta un ciclo de suspensión por BOOTTIME−MONOTONIC y espera
10 s de pulsos continuos; una interrupción >4 s reinicia la cuenta. Sin continuidad
en 60 s se omite el ciclo. No depende de hooks internos de suspensión ni hora civil.
Restaura el perfil vigente **una sola vez y directamente, sin apagado/encendido
forzado**. Un perfil apagado o con brillo cero no se enciende. La edición manual,
un nuevo ciclo o la descarga invalidan lo pendiente; los comandos no se reintentan.

Toda E/S RGB se realiza en un auxiliar que se inscribe en un scope transitorio
`ally-rgb-io-*.scope` dentro de `user.slice` ANTES de recibir comandos. Ambos procesos
verifican el cgroup y el ciclo de sueño, también antes de cada informe, rechazando
comandos antiguos. La espera de la inscripción es acotada: la respuesta de systemd
es un trabajo asíncrono y se comprueba el traslado efectivo del PID.

No hay observador logind ni monitor de reloj permanente; logind solo se consulta
al aplicar. No se instalan servicios persistentes, hooks de sueño o inhibidores,
ni se modifica el freezer. Los auxiliares de RGB quedan junto a la sesión que
SteamOS congela al suspender. El timeout no mata un auxiliar congelado ni permite
sustituir uno no terminable, que conserva su bloqueo. Ningún timeout puede resolver
por sí solo una operación no interrumpible del kernel.

Consultar estado usa caché y no lee ni escribe el RGB. Un perfil fijo se aplica
y libera trabajador/flock, sin sondeo de LED residente. Las animaciones reutilizan
un único auxiliar durante su actividad. El estado mostrado es la última aplicación
conocida: un cambio externo en reposo puede no reflejarse hasta otra operación.

Incluye una adaptación de cierre para [Decky #975](https://github.com/SteamDeckHomebrew/decky-loader/issues/975),
limitada al proceso RGB: evita el bucle IPC en EOF sin modificar el Loader ni otros plugins.
No sustituye una implementación que ya contenga comprobación EOF nativa.

No uses otro escritor RGB a la vez. ALLY RGB detecta HueSync, HHD, Ally Center, asusd
u OpenRGB y rechaza competir; no los detiene ni desinstala automáticamente. Detección por procesos
no garantiza conocer firmware u otros escritores. Ally Power puede controlar potencia de forma
independiente: ALLY RGB no usa su bloqueo ni cambia su configuración.

Cerrar el panel deja las animaciones funcionando. Descargar/desinstalar el backend detiene
su trabajador sin restaurar colores encima de otro gestor. Al escribir, una modificación externa o desaparición
del dispositivo provoca cesión, sin bucle de reimposición ni sondeo RGB en reposo.

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
y `max_brightness=255`. En kernels compatibles escribe `multi_intensity` (cuatro valores
RRGGBB) y `brightness`. Cuando el kernel recorta esos valores a 255 utiliza un fallback
hidraw limitado a color y brillo RGB: USB ASUS 0b05:1abe, interfaz 02 del mismo dispositivo,
descriptor e identidad comprobados. No modifica kernel, firmware, botones ni potencia.
La comprobación del instalador descubre esa interfaz sin enviar órdenes. E/S con Python stdlib y consultas D-Bus puntuales mediante busctl de SteamOS;
sin instalar paquetes, `termios`, pyserial ni bibliotecas HID externas.

En HID el estado informa aceptación del transporte, no lectura física del color; conserva
el último frame enviado y detecta cambios del estado sysfs/dispositivo, además de gestores
conocidos. No garantiza detectar escritores HID desconocidos. No reinstala controladores.

- [Código y guía del plugin](../components/ally-rgb/README.md).
- [Pruebas del plugin](../components/ally-rgb/VERIFICACION.md).
- [Verificación y límites de la suite](VERIFICATION.md).
- [Licencias y referencias](../components/ally-rgb/THIRD-PARTY.md).

142 pruebas automatizadas (124 Python y 18 JavaScript), compilación TypeScript/Rollup y carga
real del backend/frontend comprobadas. El usuario validó tres suspensiones/reanudaciones
en Gaming con un emulador abierto y recuperación activa, y las nuevas parejas/porcentajes.
No equivale a lectura física de colores, prueba de causa raíz de kernel ni compatibilidad
universal con otras Ally o versiones de SteamOS.
