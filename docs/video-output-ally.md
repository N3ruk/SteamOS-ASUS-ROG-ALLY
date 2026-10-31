# Video Output ALLY for DOCKs 1.0 — Decky

Nuevo componente de la colección **SteamOS ASUS ROG ALLY 1.3**. Selecciona la salida
de vídeo de Gaming desde QAM en una ASUS ROG Ally RC71L con dock. No cambia audio,
TDP, CPU/SMT, iluminación ni firmware del dock.

## Funciones

- Un panel de salidas de vídeo, sin Manage Outputs, Settings, About ni selector de audio.
- Pantalla interna identificada como **ASUS ALLY**.
- Monitores externos por etiqueta ya guardada o fabricante/modelo de su EDID;
  conector solo como alternativa si faltan datos. Los nombres iguales se distinguen.
- Estado de salida activa, cambio en curso y errores. Desde escritorio es solo lectura.
- Conserva las etiquetas y preferencias existentes. Una instalación nueva no impone
  el AOC ni otro monitor: la selección es manual. No se distribuyen EDID ni ajustes
  del equipo constructor. La API de mantenimiento conserva la configuración de vídeo
  previa; no hay página de configuración nueva.

## Requisitos y alcance

SteamOS x86_64, ROG Ally RC71L con AMDGPU/Gamescope, Decky Loader instalado **y activo**,
Python3 y aiohttp del sistema. Necesita gamescopectl, xprop, busctl, runuser y pgrep.
El instalador no resuelve dependencias ni instala o activa Decky. Otros modelos,
docks y versiones de SteamOS requieren validación; no se promete compatibilidad universal.

El plugin se identifica como **1.0**; la colección/centralizado pasa a **1.3** por
su incorporación. POWER y RGB continúan en 1.2, sin cambios de recuperación.

## Instalar, actualizar y recuperar

Descarga `Video-Output-ALLY-for-DOCKs-1.0.zip` o el centralizado 1.3, extrae y ejecuta
su `.run` desde escritorio, sin sudo. Nada se selecciona inicialmente. El individual
incluye únicamente este componente; el central ofrece siete opciones independientes.

La suite utiliza el instalador nativo de Decky con hash y solicitud exactos. Antes de
actualizar, exige un backend reconocido fuera de Gaming, sin salidas retenidas ni
operación pendiente; guarda ZIP recuperable en
`$XDG_STATE_HOME/steamos-ally-suite/output-manager/`. No detiene otros plugins ni
reinicia Steam/Loader. Una reconexión no reenvía la confirmación. Comprueba versión,
respuesta del backend y bytes instalados. Un bloqueo evita dos instalaciones de
vídeo simultáneas desde esta suite para el mismo usuario.

Para instalar directamente en Decky, `--extract fuentes` permite obtener
`fuentes/payloads/Video-Output-ALLY-for-DOCKs-1.0.zip`, el ZIP nativo con carpeta
superior `output-manager/`. **No** es el ZIP exterior que contiene el `.run`.

Si existe el **Output Manager** original, retíralo primero desde Decky conservando
sus ajustes; espera a que termine antes de pedir instalar este plugin. La suite
no ejecuta dos controladores ni sobrescribe carpetas desconocidas. Se mantiene
el nombre interno `output-manager` por compatibilidad de ajustes y del helper de
arranque previo; el nombre visible es Video Output ALLY for DOCKs. Las versiones
reconocidas de esta adaptación (1.4.0 local y 1.0) pueden actualizarse con respaldo.

Desinstalar: ajustes de Decky → Plugins → Video Output ALLY for DOCKs → desinstalar.
Las copias ZIP pueden reinstalarse con el gestor nativo. Los campos antiguos de
configuración de audio se conservan inertes para recuperación, nunca se aplican.
El instalador no modifica el wrapper de Gamescope ni instala servicios de arranque.

## Selección y recuperación de vídeo

Arquitectura `edid-mst-nudge-v1`: identidad EDID y connector-ID verificados, controlador
serializado y auxiliar temporal inscrito en `user.slice` antes de E/S. Comprueba
sesión Gaming, freezer, ciclo de suspensión y logind; no usa AMD trigger_hotplug ni
provoca reset físico/HPD del dock. Gamescope y DRM deben confirmar la salida; si falla,
revierte solo sus cambios aún reconocidos. La pantalla interna nunca se fuerza a off.
No garantiza solucionar errores físicos DPCD/enlace del dock.

Para preferencias ya configuradas: espera 10 s de sesión Gaming continua y 2 s de
topología estable; una tentativa por topología. La observación cada 2 s solo lee
metadatos del kernel. La elección manual prevalece en el ciclo actual. Al volver a
escritorio o descargar libera únicamente restricciones propias y notifica a KWin,
sin sustituir su disposición guardada. El helper de arranque sirve a integraciones
compatibles existentes; no se añade un wrapper ni preferencia de monitor al instalar.

## Código y comprobaciones

Fuentes en `components/video-output-ally/`, con TypeScript, Python, tests y lockfile.
Derivado BSD-3-Clause de Output Manager; se conservan copyrights y atribución completa
en LICENSE y NOTICE.md. El nombre nuevo no elimina la procedencia ni implica respaldo
por ASUS, Valve o los autores originales.

53 pruebas Python y 5 de interfaz, TypeScript/Rollup y probe nativo de scope sin escribir
hardware comprobados en RC71L. El panel carga y reconoce AOC/Acer/ASUS ALLY. Las pruebas
simuladas y la carga nativa **no acreditan** todavía selección física de monitores en
Gaming, dock tardío/reconexión o compatibilidad con otros equipos. No se cambia la
pantalla ni se suspende el sistema para probar el embalaje.
