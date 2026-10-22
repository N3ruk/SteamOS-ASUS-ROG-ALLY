# Dependencias y procedencia

## RyzenAdj

Proyecto original: https://github.com/FlyGoat/RyzenAdj
Versión incluida: **v0.19.0**, sin modificaciones.
Release: https://github.com/FlyGoat/RyzenAdj/releases/tag/v0.19.0

Binario oficial extraído de:
https://github.com/FlyGoat/RyzenAdj/releases/download/v0.19.0/ryzenadj-manylinux_2_28-x86_64.tar.gz

SHA256 del archivo oficial (contrastado con `digest` de la API de GitHub):
`d04547f111c6af3e40d3f210468adb884561618ddade0b640d90e50c88d03444`

Fuentes completas incluidas en `source/RyzenAdj-v0.19.0-source.tar.gz`, obtenidas de:
https://codeload.github.com/FlyGoat/RyzenAdj/tar.gz/refs/tags/v0.19.0

SHA256:
`d1998b6c2d1b564f5d43c786cbf764ca9a1d8bb213e2001f98f611ead3087c7e`

RyzenAdj se distribuye bajo LGPL-3.0; se adjuntan LGPL-3.0 y GPL-3.0.
Conserva los avisos de copyright de las fuentes. El README/CMake originales y los workflows
incluidos describen la compilación. El ejecutable usa las bibliotecas del sistema (libc, libpci);
no se redistribuyen dichas bibliotecas. Puede sustituirse/recompilarse el ejecutable y reconstruir
el paquete. Ally Power lo invoca como proceso externo; no enlaza con su biblioteca.

## Interfaz

Python, GTK4, PyGObject, GdkPixbuf, GLib/Gio, KDE y polkit son dependencias del sistema, no
se redistribuyen aquí. `status-notifier.xml` describe la interfaz pública StatusNotifierItem.
El código propio de Ally Power y sus herramientas se entrega con licencia MIT (ver licenses/).

## Imágenes y marcas

`icon.svg` es el icono simple creado para esta app. `icon-gaming.png` es la imagen aportada
por el usuario. La licencia MIT del código no concede derechos sobre imágenes de terceros
ni sobre marcas ASUS/ROG, Steam/Valve u otras representadas. El paquete no está afiliado ni
avalado por sus titulares; antes de publicarlo comercialmente revisa los derechos de esa imagen.
