# Licencias y procedencia

## Código propio

El instalador centralizado, nuevos instaladores de lanzadores, scripts, pruebas y documentación propios se distribuyen bajo MIT: [LICENSE](LICENSE). Ally Power, su plugin, ALLY RGB y Confianza Bluetooth conservan sus avisos MIT en cada subdirectorio. El SVG del mando de Confianza Bluetooth está cubierto por su licencia original.

## Iconos aportados

Los PNG `GAMEMODE.png`, `steamos-default-mode-toggle.png` e `icon-gaming.png` se distribuyen como recursos aportados para este proyecto. **No** se atribuyen al código MIT ni se otorgan por esta documentación derechos sobre marcas o diseños de terceros. Se conservan tal como fueron aportados. Su presencia no implica afiliación con Valve, ASUS o Sony.

## RyzenAdj

Proyecto original: https://github.com/FlyGoat/RyzenAdj — versión 0.19.0. Binario oficial x86_64 y fuentes completas correspondientes se incluyen en Ally Power/Decky, con avisos LGPL-3.0/GPL-3.0 según corresponda. Véanse sus `THIRD-PARTY.md`, `licenses/` y archivos fuente. No se reemplazan esas condiciones por la licencia de la suite.

Entradas oficiales fijadas para Ally Power:

- `ryzenadj-manylinux_2_28-x86_64.tar.gz`: `d04547f111c6af3e40d3f210468adb884561618ddade0b640d90e50c88d03444`.
- `RyzenAdj-v0.19.0-source.tar.gz`: `d1998b6c2d1b564f5d43c786cbf764ca9a1d8bb213e2001f98f611ead3087c7e`.

## Plataformas y bibliotecas

- Decky Loader y template: https://github.com/SteamDeckHomebrew/decky-loader y https://github.com/SteamDeckHomebrew/decky-plugin-template. API local comprobada contra Loader 3.3.0, no distribuido ni instalado por la suite.
- Frontend Decky: dependencias/versiones/licencias fijadas en `components/ally-power-decky/package-lock.json`; se mantiene el código fuente TypeScript y build reproducible mediante npm. No se distribuye `node_modules`. Los textos de licencia de las dependencias de npm se conservan en `components/ally-power-decky/licenses/npm/`, también dentro del ZIP nativo del plugin.
- GTK/PyGObject, BlueZ, KDialog, steamosctl y bibliotecas del sistema se utilizan desde SteamOS, no se empaquetan como copias propias.
- Adaptador de API Decky escrito para esta suite sobre `aiohttp`, biblioteca del sistema disponible en su instalación; no se distribuye ni instala automáticamente.

La consulta previa de alternativas favoreció reutilizar los instaladores existentes y la API de Decky en vez de un segundo instalador privilegiado. La interfaz central propia cubre la selección y agrupación específicas solicitadas por el usuario.

## ALLY RGB

Código propio MIT y dependencias de Decky fijadas en `components/ally-rgb/package-lock.json`,
con fuentes TypeScript/Python y licencias en su subdirectorio. React y UI se proporcionan
por Decky; no se distribuye `node_modules`. Referencias al ABI de la Ally, HueSync y
los avisos completos en [components/ally-rgb/THIRD-PARTY.md](components/ally-rgb/THIRD-PARTY.md).
No se incluye código de HueSync, pyserial, controladores HID o gestores de potencia en este plugin.
