# Confianza Bluetooth

App GTK4 sencilla para listar los dispositivos BlueZ con `Trusted=true` y retirarles
la confianza. Nombre en el menú de KDE: **Confianza Bluetooth**.

- Lista nombre, dirección MAC, adaptador, conexión y emparejamiento por cable cuando corresponde.
- Búsqueda por nombre/MAC y actualización automática; botón Actualizar para reintentar.
- Quitar confianza muestra una confirmación con el nombre y MAC exactos.
- Recomprueba la identidad del dispositivo, cambia únicamente `org.bluez.Device1.Trusted=false`
  y vuelve a leer la propiedad para verificar el resultado.
- No olvida emparejamientos, no elimina claves, no bloquea ni desconecta dispositivos,
  no escanea, no cambia adaptadores y no reinicia Bluetooth.
- No utiliza sudo, shell ni ayudantes root; trabaja con los permisos de la sesión local de KDE.
- Los nombres remotos son texto, nunca comandos ni markup.

Para el PS3: quita la confianza del mando correcto, desconecta/reconecta su USB y acepta
la solicitud del escritorio. Después retira el USB y pulsa PS. La app no garantiza que se
vincule si existe otro problema de hardware, autorización o servicio Bluetooth.

Icono vectorial propio inspirado en un mando PS3, con dos sticks simétricos y distintivo Bluetooth.
No es software oficial de Sony. Sin servicios de inicio ni permanencia en segundo plano.

Código en `~/.local/share/bluetooth-trust-manager/`; lanzador en
`~/.local/share/applications/local.BluetoothTrustManager.desktop`.

Pruebas sin modificar dispositivos: `python3 -m unittest -v test_app` desde esta carpeta.
Las pruebas de mutación usan un bus simulado; la validación del listado real es de solo lectura.
