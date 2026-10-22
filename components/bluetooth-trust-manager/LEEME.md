# Confianza Bluetooth 1.0.0 — SteamOS

Lista dispositivos Bluetooth de confianza y permite retirarles la confianza con una confirmación.
No borra emparejamientos ni desconecta dispositivos. Incluye icono vectorial de mando PS3.

## Instalación fácil

1. Copia `Confianza-Bluetooth-1.0.0-SteamOS.run` al equipo y entra en el modo escritorio.
2. Dolphin → Propiedades → Permisos → **Es ejecutable** (si no está marcado).
3. Doble clic → **Ejecutar**, confirma y busca **Confianza Bluetooth** en el menú de KDE.

No usa sudo, no solicita contraseña de administrador, no modifica el sistema de solo lectura
y no cambia dispositivos durante la instalación. No depende del usuario `deck` ni del modelo
de equipo: sirve para Steam Deck, Ally y otros equipos con SteamOS y las dependencias indicadas.

Si Dolphin abre el archivo como texto, abre Konsole en su carpeta:

```sh
bash ./Confianza-Bluetooth-1.0.0-SteamOS.run
```

## Requisitos y alcance

SteamOS con KDE Plasma 6, Python 3, GTK4 y PyGObject (`python-gobject`), y BlueZ activo para
usar la app. El instalador comprueba dependencias; si faltan, se detiene e informa. No instala
paquetes ni necesita Internet. No se garantiza soporte para todas las versiones antiguas o
instalaciones modificadas de SteamOS. La app es Python y no incluye binarios específicos de una APU.

La app original fue probada por el usuario en este SteamOS. El paquete se prueba además en
directorios aislados; no se ha ejecutado en todas las variantes de SteamOS ni en otro dispositivo.

## Uso y seguridad

- Busca por nombre o MAC; cada dispositivo muestra su dirección y adaptador.
- **Quitar confianza** pide confirmación, comprueba la identidad, escribe exclusivamente
  `org.bluez.Device1.Trusted=false` y verifica el resultado.
- No ejecuta `RemoveDevice`, no borra claves, no apaga Bluetooth y no modifica la bandeja de KDE.
- Para PS3, tras quitar confianza desconecta/reconecta USB y acepta la autorización del escritorio.
  Después retira el USB y pulsa PS para conectar por Bluetooth.
- Si una distribución deniega permisos, se muestra el error; no se instalan excepciones de seguridad.
- No hay servicios, arranque automático ni icono de bandeja propio. Al cerrar la app termina.
  El icono Bluetooth habitual de la bandeja pertenece a KDE y es independiente.

## Actualizar y desinstalar

Cierra la app y vuelve a ejecutar el instalador. Se guarda una copia de los archivos anteriores
en `~/.local/share/bluetooth-trust-manager.backup-*`.

Menú KDE → **Desinstalar Confianza Bluetooth**, o:

```sh
bash ./Confianza-Bluetooth-1.0.0-SteamOS.run --uninstall
```

La desinstalación mueve los archivos a una copia recuperable `.removed-*`, sin tocar dispositivos.
Las copias no se eliminan automáticamente. Si defines `XDG_DATA_HOME`, se utiliza esa carpeta
en lugar de `~/.local/share`. La instalación está en el home y no depende de cambios en `/usr`.

## Comprobar o revisar el código

```sh
bash ./Confianza-Bluetooth-1.0.0-SteamOS.run --check
bash ./Confianza-Bluetooth-1.0.0-SteamOS.run --extract ./Confianza-extraida
sha256sum -c SHA256SUMS
```

La carpeta de extracción debe ser nueva. El `.tar.gz` alternativo contiene los mismos archivos;
tras extraerlo, `python3 installer.py` inicia la instalación. El checksum detecta corrupción,
no sustituye una firma: usa un paquete de origen conocido.

Fuentes y pruebas incluidas. Desde la carpeta extraída:
`PYTHONPATH=payload:. python3 -m unittest -v test_app test_installer`.
`python3 build.py` reconstruye el instalador. Las pruebas de retirada de confianza usan un bus
simulado; no cambian dispositivos reales. Dependencias del sistema no redistribuidas.

Licencia MIT para código/icono propios. No es software oficial de Sony, Valve ni KDE.
