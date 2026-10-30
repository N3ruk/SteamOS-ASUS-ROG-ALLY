# SteamOS ASUS ROG ALLY 1.2

Nueva release del instalador centralizado **1.2** y **ALLY RGB 1.2**. Los demás
componentes conservan sus versiones y sus cinco paquetes anteriores sin cambios.
La release v1.0.0 permanece disponible y no se reemplaza.

## ALLY RGB 1.2

- Recuperación opcional al arrancar/despertar: confirma disponibilidad de la sesión
  y del dispositivo, espera 10 segundos y apaga/restaura una sola vez el perfil.
- Cancelación por nueva suspensión, edición manual, cambio de dispositivo o descarga.
- Acceso RGB aislado, timeouts y bloqueo compartido con sus propios escritores;
  sin servicios nuevos, inhibidores ni reinicios USB.
- Corrección de cierre IPC de Decky limitada al proceso RGB; no modifica el Loader.
- Conserva brillo, colores, velocidades, transiciones y selección de las cuatro zonas.
- Sin perfil previo válido no aplica luces al cargar. Sigue limitado a ROG Ally RC71L.

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

108 pruebas Python RGB y 14 JavaScript, TypeScript/Rollup, pruebas de la suite y
verificación integral de los siete paquetes sin instalar componentes en el host.
Recarga del backend RGB activo comprobada en 0,1 s sin SIGKILL. Las pruebas no
acreditan lectura física de colores ni una suspensión real en Gaming; no se declara
resuelta la causa de los bloqueos anteriores ni compatibilidad universal con otras Ally.
