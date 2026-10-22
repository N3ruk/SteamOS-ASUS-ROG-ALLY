# Confianza Bluetooth — 1.0.0

Lista dispositivos Bluetooth marcados como **de confianza**, busca por nombre/dirección y permite retirar esa confianza a un dispositivo exacto, previa confirmación con su dirección.

Especialmente útil para **mandos PS3/Sixaxis**: después de desvincular un mando, BlueZ puede seguir considerándolo de confianza y omitir la solicitud de autorización por USB. Quitar esa confianza y reconectar el cable puede hacer reaparecer la autorización. Después de aceptarla, desconecta el cable y pulsa PS para probar Bluetooth. No garantiza reparar cualquier problema de emparejamiento o cualquier mando compatible/clon.

Solo cambia la propiedad `Trusted` del dispositivo elegido. **No** borra claves, no usa `RemoveDevice`, no apaga Bluetooth y no elimina otros dispositivos. No es un administrador general de emparejamientos.

## Instalación / quitar

Individual: `Confianza-Bluetooth-1.0.0.zip` o centralizado. Se reutiliza el `.run` original sin modificar la app. Requiere SteamOS KDE, Python 3 con PyGObject/GTK4, BlueZ y acceso a D-Bus. Sin sudo. Cierra la app antes de reinstalarla.

Se instala solo para el usuario; al instalar/desinstalar no se consulta ni cambia la confianza de ningún mando. Desinstalación desde su entrada de menú o `.run` original con `--uninstall`; conserva una copia recuperable.

## Fuentes

[`components/bluetooth-trust-manager`](../components/bluetooth-trust-manager); [guía original](../components/bluetooth-trust-manager/LEEME.md). Código y SVG del mando bajo MIT según su licencia. La comunicación con BlueZ utiliza la API D-Bus del sistema, no un servicio nuevo de la suite.
