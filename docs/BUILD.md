# Construcción y pruebas

## Fuente del proyecto

El repositorio incluye fuentes de las siete piezas, recursos, pruebas, instaladores originales fijados y fuentes/licencias correspondientes de RyzenAdj. No se incluyen `node_modules`, credenciales, referencias de diagnóstico ni copias de tu equipo. Los binarios oficiales incorporados conservan sus avisos; no se descargan al instalar.

## Generar los ocho ZIP

Desde la raíz, con Python 3.10+ (SteamOS actual):

```bash
python3 build.py
python3 -m unittest discover -s tests -v
python3 verify_packages.py
```

La comprobación correcta de la lista relativa es:

```bash
(cd release && sha256sum -c SHA256SUMS)
```

`release/` contiene centralizado, siete individuales y `SHA256SUMS`. Cada ZIP incluye un `.run` autoextraíble sin dependencias de la carpeta original. Fechas y orden de archivos del paquete son fijos para obtener bytes iguales a partir de las mismas fuentes y entradas. La integridad SHA256 comprueba corrupción, no identidad criptográfica del autor.

## Reconstruir aplicaciones

El build central empaqueta los instaladores originales fijados en `payloads/`; editar `components/` por sí solo **no cambia esos binarios**. Para modificarlos:

- Escritorio: `cd components/ally-power; python3 build.py`; copiar su `.run` desde `dist/` a `payloads/` y actualizar versión/nombre en `engine.py` y `build.py` si cambia. Ver `REBUILD.md`.
- ALLY RGB: en `components/ally-rgb`, ejecutar `npm ci`, `npm run typecheck`, `npm run build`, `python3 build.py`. Copiar `release/ALLY-RGB-1.2.zip` a `payloads/` y recalcular su entrada en `payloads/SHA256SUMS`. Es el ZIP nativo; el ZIP individual exterior se genera con el build de la suite.
- Bluetooth: `cd components/bluetooth-trust-manager; python3 build.py`; copiar el `.run` de `dist/` a `payloads/`.
- Decky: requiere Node/npm compatibles con las dependencias bloqueadas. En `components/ally-power-decky`, ejecutar `npm ci --ignore-scripts`, `npm run typecheck`, `npm run build`, `python3 build.py`. Copiar el ZIP de `release/` a `payloads/`. No hace falta Node en el equipo que instala.
- Lanzadores: se empaquetan directamente desde `components/return-gaming`, `components/default-mode` e `installer/launchers.py`. No necesitan compilación.

Después de sustituir binarios, revisa las entradas y renueva sus hashes con `(cd payloads && sha256sum *.run *.zip > SHA256SUMS)`. No regeneres hashes para ignorar una corrupción o un cambio no revisado.

Regenera finalmente `python3 build.py` para renovar manifests, `.run`, ZIP y checksums. Las pruebas no escriben TDP/SMT ni invocan el cambio real de arranque.

## Pruebas de componentes

Ejecutar en cada directorio con `/usr/bin/python3`; las pruebas de las apps gráficas necesitan PyGObject/GTK4 disponibles:

```bash
(cd components/ally-power && PYTHONPATH=src:packaging:. python3 -m unittest discover -s tests -v)
(cd components/ally-power-decky && python3 -m unittest discover -s tests -v)
(cd components/ally-power-decky && node --test tests/test_live_queue.mjs tests/test_steam_tdp.mjs tests/test_session_frontend.mjs)
(cd components/ally-rgb && python3 -m unittest discover -s tests -v)
(cd components/ally-rgb && node --test tests/test_queue.mjs tests/test_ui.mjs)
(cd components/bluetooth-trust-manager && python3 -m unittest -v test_installer)
(cd components/bluetooth-trust-manager/payload && python3 -m unittest -v test_app)
```

Las fuentes extraídas del centralizado incluyen `build.py` y todas las piezas. Las fuentes del individual solo contienen su componente: para reconstruir los ocho paquetes necesitas el checkout completo o extraer el centralizado.

## Publicación en GitHub

`publish.py` requiere GitHub CLI oficial autenticada y una elección explícita de visibilidad. No se publica nada durante `build.py` ni durante las pruebas.

```bash
gh auth login --hostname github.com --git-protocol https --web
python3 publish.py --owner TU_USUARIO --visibility public
# O --visibility private: nunca se asume público por defecto.
```

Debe ejecutarse sobre un checkout limpio, revisado y con commit en `main`. Comprueba los ocho paquetes, crea `SteamOS-ASUS-ROG-ALLY` si no existe, conserva un `origin` ajeno sin modificarlo, empuja sin force y crea `v1.3` con los ocho ZIP y `SHA256SUMS`. No imprime tokens, no modifica la configuración global de git y no reemplaza una release existente. Descarga de nuevo los nueve assets publicados y comprueba que sus hashes coincidan con los locales. Crear el repositorio exige permisos de GitHub adicionales a los de un conector que solo lee/escribe código en repositorios ya existentes.


## Integración de vídeo: colección 1.3 / plugin 1.0

Nuevo release v1.3 por añadir Video Output ALLY for DOCKs 1.0. Las aplicaciones
previas conservan versiones y seis ZIP individuales. Para esta publicación:

```bash
(cd components/video-output-ally && npm ci --ignore-scripts && npm run typecheck && npm run build)
(cd components/video-output-ally && python3 -m unittest discover -s tests -v && node --test tests/frontend.test.mjs)
python3 components/video-output-ally/build.py
# Copiar release/Video-Output-ALLY-for-DOCKs-1.0.zip del componente a payloads/.
# Renovar únicamente su entrada fijada de payloads/SHA256SUMS tras revisar el ZIP.
python3 build.py --only central video-output-ally
python3 -m unittest discover -s tests -v
python3 verify_packages.py
(cd release && sha256sum -c SHA256SUMS)
```

Un checkout sin los seis individuales previos puede reconstruir los ocho con
`python3 build.py`; para conservar exactamente los publicados en v1.2, descarga
esos seis individuales primero y verifica sus hashes. El central 1.3 y el nuevo
individual comparten ZIP nativo y fuentes. El nativo tiene carpeta `output-manager/`
y manifest SHA256; no distribuye settings/EDID/wrapper del host. Las licencias npm
están en `licenses/npm/`; se mantiene BSD-3-Clause y procedencia de Output Manager.

Publicar main sin force y crear v1.3 apuntando al commit comprobado. No editar,
retaggear ni reemplazar v1.2/v1.0.0. Nueve assets: ocho ZIP + SHA256SUMS. Verificar
la descarga autenticada y el acceso público y conservar los seis individuales.
La versión central está en installer/version.py; vídeo en package.json/lock raíz,
main.py y catálogo. No sustituir cadenas 1.2 globalmente: POWER/RGB siguen en 1.2.

## Referencia histórica: refrescos de RGB en v1.2

Después de reconstruir el ZIP nativo RGB y renovar su hash fijado:

```bash
python3 build.py --only central ally-rgb
python3 verify_packages.py
(cd release && sha256sum -c SHA256SUMS)
```

Genera `SteamOS-ASUS-ROG-ALLY-1.2.zip` y `ALLY-RGB-1.2.zip`, y conserva los otros
cinco individuales byte a byte. `--only` necesita esos cinco ZIP previos en `release/`;
pueden descargarse de v1.0.0. Desde un checkout nuevo, `python3 build.py` reconstruye
los siete a partir de las fuentes actuales (los cinco reconstruidos pueden cambiar
su envoltorio/documentación, sin cambiar las aplicaciones fijadas).

La versión del centralizado se define en `installer/version.py`, importada por build,
interfaz y publicación; la versión RGB está en su package.json/backend y en el catálogo.
El ZIP individual exterior RGB es un instalador `.run`: el ZIP nativo Decky está dentro
del payload. El centralizado incluye exactamente ese mismo ZIP nativo, fuentes y licencias.

## Referencia histórica: refresco de ALLY POWER en v1.2

El plugin, catálogo, ZIP nativo y envoltorio individual POWER usan **1.2**.
Reconstruir explícitamente `components/ally-power-decky` con sus dependencias
bloqueadas, pruebas Python/JS, TypeScript y Rollup; copiar
`release/Ally-Power-Decky-1.2.zip` a `payloads/` y renovar su hash. Eliminar del
catálogo y de los payloads la entrada anterior 1.1.0, no conservar dos variantes
como si fueran la misma aplicación.

```bash
python3 build.py --only central ally-power-decky
python3 -m unittest discover -s tests -v
python3 verify_packages.py
(cd release && sha256sum -c SHA256SUMS)
```

Conserva los otros cinco individuales byte a byte, incluido RGB 1.2. Verifica
todos los archivos del ZIP nativo contra sus fuentes y distingue su nombre,
idéntico al exterior, por la estructura interna: el nativo contiene
`ally-power-decky/`, el exterior contiene el `.run`.

La release v1.2 ya existe. `publish.py` es solo para una release nueva y rechaza
reemplazar una existente. Un refresco autorizado del mismo v1.2 debe respaldar
metadata/assets y preservar tag, título, ID y los assets ajenos. Para POWER,
tras validación real Gaming del usuario, se sustituye el centralizado, se publica
`Ally-Power-Decky-1.2.zip` y se retira únicamente el antiguo individual 1.1.0 de
este release; se renueva SHA256SUMS y su descripción con docs/RELEASE.md. El cambio
de nombre POWER a 1.2 fue solicitado expresamente. Para refrescos solo RGB se
conservan los nombres existentes y se construye `--only central ally-rgb`.

Empujar main sin force ni retag. No crear release, discusión ni anuncio nuevos.
Descargar los ocho assets y verificar hashes, metadata y los cinco assets ajenos;
v1.0.0 debe permanecer íntegra. No incluye paquetes 1.3.x ni exige reinstalar o
alterar hardware del equipo constructor para comprobar el embalaje.
