# SteamOS ASUS ROG ALLY 1.2

Instalador centralizado **1.2**, **Ally Power Decky 1.2** y **ALLY RGB 1.2**.
Los otros cinco paquetes individuales conservan sus archivos sin cambios.
La release v1.0.0 permanece disponible y no se reemplaza.

## ALLY RGB 1.2

- Selector de edición: todas, parejas 1 y 2 / 3 y 4 / **2 y 3 / 1 y 4**, o zonas individuales. Cada zona conserva su efecto, color, velocidad y transición; seleccionar otro grupo no aplica iluminación ni detiene las demás zonas.
- Porcentajes visibles 0–100 % junto a cada canal de color, incluidos Color inicial y Color final de Transición. La visualización se redondea, pero se conservan los 256 niveles RGB.
- Velocidad indicada de 0 % (mínima) a 100 % (máxima), sin cambiar los ritmos ni la configuración previamente guardada.

### Recuperar al despertar/encender

El backend detecta la suspensión real por BOOTTIME−MONOTONIC al recibir pulsos ligeros de Steam, también con QAM cerrado. Cuenta 10 s de pulsos continuos antes de aplicar una sola vez el perfil vigente. Si los pulsos se interrumpen más de 4 s, reinicia la cuenta; si no logra continuidad en 60 s, omite ese ciclo. Un perfil apagado o con brillo cero no se enciende automáticamente.

La restauración envía directamente brillo y cuatro zonas: **no fuerza un apagado/encendido temporal**. Edición manual, descarga o nuevo ciclo de suspensión invalidan el intento; los comandos fallidos no se reintentan en bucle.

Toda E/S RGB se ejecuta en un auxiliar inscrito y verificado, antes de recibir comandos, en un scope transitorio de `user.slice`, junto a la sesión que SteamOS congela al suspender. Padre e hijo verifican cgroup/ciclo de sueño y rechazan comandos antiguos. No instala servicios persistentes, hooks de sueño ni inhibidores. No hay observador logind ni monitor periódico de reloj; logind solo se consulta puntualmente al aplicar. El estado del panel usa caché y los perfiles fijos no dejan un auxiliar, bloqueo o sondeo RGB residente. Las animaciones reutilizan un único auxiliar durante su actividad.

Se han validado tres suspensiones/reanudaciones satisfactorias en Gaming, con un
emulador abierto y la función activa, y la interfaz de las nuevas parejas y
porcentajes. Ese resultado no demuestra una causa concreta de los antiguos bloqueos
ni compatibilidad universal. El transporte HID aceptado no es lectura física del color.

La recuperación RGB y su paquete permanecen sin cambios en este refresco de POWER.

## Ally Power Decky 1.2

- Mantiene TDP y CPU/SMT independientes, cambios en tiempo real, recuadro único de estado y control coordinado con el TDP nativo de Steam. La topología física conserva sus comprobaciones para CPUs offline.
- Toda E/S de CPU/RyzenAdj empieza después de inscribir y verificar el auxiliar en un scope transitorio de `user.slice`. Las órdenes están ligadas a la sesión y al ciclo de suspensión; las guardas de freezer y reloj rechazan órdenes antiguas. EOF, timeout y cierre del auxiliar no restauran hardware.

### Preparación antes de suspender

Antes de permitir SMT apagado o menos núcleos/hilos, adquiere un inhibidor logind **delay**, nunca block. Al recibir `PrepareForSleep(true)`, invalida las órdenes y activa SMT/todos los hilos de la CPU que todavía posee, antes del freezer/kernel PM. No modifica TDP, RGB, HID ni MCU durante esta preparación.

El acceso D-Bus tipado vive en un auxiliar de Python del sistema que solo maneja metadatos y el FD del inhibidor; las escrituras de hardware siguen en `user.slice`. La preparación tiene un límite de 2,2 s y el auxiliar libera el FD como máximo a los 2,5 s, además del máximo propio de logind. No instala servicios persistentes, hooks de sueño ni modifica Loader. Al salir de Gaming o descargar el plugin también normaliza la CPU aún poseída, sin sobrescribir a otro gestor.

### Recuperar ajustes al despertar

Nuevo interruptor optativo **Recuperar ajustes al despertar**, con cuenta atrás y resultado en el recuadro de estado. Antes de suspender conserva **en memoria** los ajustes que controlaba POWER. Tras reanudar espera **10 s de pulsos reales continuos de Steam en Gaming**, incluso con QAM cerrado, manteniendo CPU completa durante la espera. Un hueco mayor de 4 s reinicia la cuenta; el intento caduca a los 60 s.

Recupera una sola vez **TDP primero y CPU/SMT después**. Respeta el límite actual de batería/cargador y solo recupera TDP si Steam no ha retomado su control ni cambiado el perfil nativo. Entre etapas vuelve a leer Steam y, antes de reducir CPU, comprueba la configuración normalizada y readquiere la protección logind. TDP solo no cambia CPU ni mantiene un inhibidor de retraso.

Edición manual, otra suspensión, salida de Gaming, cambio de juego, control de escritorio o gestor competidor cancelan el intento. Si Steam aún no identifica el juego, espera sin aplicar sus ajustes al menú. No hay reintentos en bucle. Solo se guarda si la opción está activada: **no se guardan perfiles CPU/TDP ni se aplican al arrancar o recargar**. Con la opción apagada, CPU queda completa tras despertar hasta una nueva acción manual.

El usuario ha confirmado el funcionamiento en Gaming, primero de la preparación y después de la recuperación automática. No se atribuye un número de ciclos a esta última confirmación ni compatibilidad universal. Se mantiene **1.2**, también en el ZIP nativo y el instalador individual, reutilizando este mismo release.

## Componentes incluidos

| Componente | Versión |
|---|---|
| Instalador centralizado | 1.2 |
| ALLY RGB — Decky | 1.2 |
| Volver al modo Gaming | 1.0.0 |
| Alternar arranque SteamOS | 1.0.0 |
| Ally Power Escritorio | 1.0.0 |
| Ally Power Decky | 1.2 |
| Confianza Bluetooth | 1.0.0 |

## Descargas

- `SteamOS-ASUS-ROG-ALLY-1.2.zip` — centralizado con seis componentes opcionales.
- `ALLY-RGB-1.2.zip` — instalador individual autónomo RGB; incluye el ZIP nativo Decky.
- `Volver-al-Modo-Gaming-1.0.0.zip`.
- `Alternar-Arranque-SteamOS-1.0.0.zip`.
- `Ally-Power-Escritorio-1.0.0.zip`.
- `Ally-Power-Decky-1.2.zip` — instalador individual autónomo POWER; incluye el ZIP nativo Decky 1.2.
- `Confianza-Bluetooth-1.0.0.zip`.
- `SHA256SUMS` — hashes de los siete ZIP.

Extrae el ZIP y ejecuta su `.run` en escritorio **sin sudo**. Todo empieza desmarcado.
Cada paquete incluye fuentes, documentación y licencias, accesibles mediante `--extract`.
La suite no instala ni activa Decky ni cambia arranque/TDP/SMT/Bluetooth por sí sola.
Las apps originales conservan sus confirmaciones. El plugin RGB puede restaurar un perfil
previo si su opción de recuperación estaba habilitada.

Para instalar RGB directamente desde Decky, extrae el `.run` con `--extract fuentes`:
`fuentes/payloads/ALLY-RGB-1.2.zip` es el ZIP nativo de carpeta superior `ally-rgb/`.
La suite no reemplaza un plugin RGB que esté controlando luces o recuperándose; en
ese caso utiliza la gestión nativa de Decky. Los ajustes guardados se conservan.

Para POWER, `fuentes/payloads/Ally-Power-Decky-1.2.zip` es el ZIP nativo con carpeta
superior `ally-power-decky/`, distinto del ZIP exterior de descarga. El adaptador
reconoce POWER 1.2, respalda la instalación anterior y rechaza sustituirla si
controla hardware o tiene una recuperación pendiente. Este refresco no reinstala
plugins ni cambia los ajustes del equipo usado para preparar los paquetes.

## Comprobaciones y límites

115 pruebas Python POWER y 16 JavaScript; 124 pruebas Python RGB y 18 JavaScript,
TypeScript/Rollup, 48 pruebas de la suite y verificación integral de los siete
paquetes sin instalar componentes en el host.
Recarga del backend RGB activo comprobada en 0,1 s sin SIGKILL; validación del usuario
en Gaming y de la interfaz indicada arriba. Las pruebas no acreditan lectura física
de colores ni compatibilidad universal con otras Ally o versiones de SteamOS.
