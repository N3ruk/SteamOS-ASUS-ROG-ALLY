# Dependencias y licencias

El código propio y el motor derivado de Ally Power se distribuyen bajo MIT
(`licenses/Ally-Power-MIT.txt`). La interfaz usa el formato y las bibliotecas
oficiales de Decky: `@decky/api`, `@decky/ui` y `@decky/rollup`; sus avisos están
en los paquetes npm correspondientes y se preservan en el bundle generado.
React y la interfaz de Decky se proporcionan por el propio Loader, no se empaqueta
otra instancia de React.

RyzenAdj v0.19.0, sin modificaciones, procede de:
https://github.com/FlyGoat/RyzenAdj/releases/tag/v0.19.0

Archivo oficial de binarios: `ryzenadj-manylinux_2_28-x86_64.tar.gz`.
SHA256 del archivo upstream:
`d04547f111c6af3e40d3f210468adb884561618ddade0b640d90e50c88d03444`.

Fuentes completas: `licenses/RyzenAdj-v0.19.0-source.tar.gz`.
SHA256 de las fuentes:
`d1998b6c2d1b564f5d43c786cbf764ca9a1d8bb213e2001f98f611ead3087c7e`.

Se incluyen los textos LGPL-3.0 y GPL-3.0. El programa invoca RyzenAdj como
proceso separado. Se puede recompilar y sustituir el ejecutable conservando sus
licencias; la construcción se describe en las fuentes. Las bibliotecas del
sistema (libc, libpci, etc.) no se redistribuyen. La alternativa preferida en este
equipo es el RyzenAdj ya instalado por la app de escritorio, que no se incluye
ni modifica en este ZIP.

Python y Decky Loader son dependencias del sistema. Este plugin no usa GTK,
polkit, un servicio systemd propio ni la imagen PNG de la app de escritorio.
Los nombres ASUS/ROG, Steam y Decky pertenecen a sus respectivos titulares;
este proyecto no está afiliado ni avalado por ellos.
