# SteamOS ASUS ROG ALLY 1.2

Instalador centralizado **1.2** y **ALLY RGB 1.2**. Los demás
componentes conservan sus versiones y sus cinco paquetes anteriores sin cambios.
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

Versión y release se mantienen en **1.2**. Sin cambios en ALLY POWER ni en otros componentes de la suite.

## Componentes incluidos

| Componente | Versión |
|---|---|
| Instalador centralizado | 1.2 |
| ALLY RGB — Decky | 1.2 |
| Volver al modo Gaming | 1.0.0 |
| Alternar arranque SteamOS | 1.0.0 |
| Ally Power Escritorio | 1.0.0 |
| Ally Power Decky | 1.1.2 (envoltorio individual 1.1.0 conservado) |
| Confianza Bluetooth | 1.0.0 |

## Descargas

- `SteamOS-ASUS-ROG-ALLY-1.2.zip` — centralizado con seis componentes opcionales.
- `ALLY-RGB-1.2.zip` — instalador individual autónomo RGB; incluye el ZIP nativo Decky.
- `Volver-al-Modo-Gaming-1.0.0.zip`.
- `Alternar-Arranque-SteamOS-1.0.0.zip`.
- `Ally-Power-Escritorio-1.0.0.zip`.
- `Ally-Power-Decky-1.1.0.zip`.
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

## Comprobaciones y límites

124 pruebas Python RGB y 18 JavaScript, TypeScript/Rollup, 46 pruebas de la suite y
verificación integral de los siete paquetes sin instalar componentes en el host.
Recarga del backend RGB activo comprobada en 0,1 s sin SIGKILL; validación del usuario
en Gaming y de la interfaz indicada arriba. Las pruebas no acreditan lectura física
de colores ni compatibilidad universal con otras Ally o versiones de SteamOS.
