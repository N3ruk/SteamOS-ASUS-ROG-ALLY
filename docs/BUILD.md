# Construcción y pruebas

## Fuente del proyecto

El repositorio incluye fuentes de las seis piezas, recursos, pruebas, instaladores originales fijados y fuentes/licencias correspondientes de RyzenAdj. No se incluyen `node_modules`, credenciales, referencias de diagnóstico ni copias de tu equipo. Los binarios oficiales incorporados conservan sus avisos; no se descargan al instalar.

## Generar los siete ZIP

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

`release/` contiene centralizado, seis individuales y `SHA256SUMS`. Cada ZIP incluye un `.run` autoextraíble sin dependencias de la carpeta original. Fechas y orden de archivos del paquete son fijos para obtener bytes iguales a partir de las mismas fuentes y entradas. La integridad SHA256 comprueba corrupción, no identidad criptográfica del autor.

## Reconstruir aplicaciones

El build central empaqueta los instaladores originales fijados en `payloads/`; editar `components/` por sí solo **no cambia esos binarios**. Para modificarlos:

- Escritorio: `cd components/ally-power; python3 build.py`; copiar su `.run` desde `dist/` a `payloads/` y actualizar versión/nombre en `engine.py` y `build.py` si cambia. Ver `REBUILD.md`.
- ALLY RGB: en `components/ally-rgb`, ejecutar `npm ci`, `npm run typecheck`, `npm run build`, `python3 build.py`. Copiar `release/ALLY-RGB-1.0.0.zip` a `payloads/` y recalcular su entrada en `payloads/SHA256SUMS`. Es el ZIP nativo; el ZIP individual exterior se genera con el build de la suite.
- Bluetooth: `cd components/bluetooth-trust-manager; python3 build.py`; copiar el `.run` de `dist/` a `payloads/`.
- Decky: requiere Node/npm compatibles con las dependencias bloqueadas. En `components/ally-power-decky`, ejecutar `npm ci`, `npm run typecheck`, `npm run build`, `python3 build.py`. Copiar el ZIP de `release/` a `payloads/`. No hace falta Node en el equipo que instala.
- Lanzadores: se empaquetan directamente desde `components/return-gaming`, `components/default-mode` e `installer/launchers.py`. No necesitan compilación.

Después de sustituir binarios, revisa las entradas y renueva sus hashes con `(cd payloads && sha256sum *.run *.zip > SHA256SUMS)`. No regeneres hashes para ignorar una corrupción o un cambio no revisado.

Regenera finalmente `python3 build.py` para renovar manifests, `.run`, ZIP y checksums. Las pruebas no escriben TDP/SMT ni invocan el cambio real de arranque.

## Pruebas de componentes

Ejecutar en cada directorio con `/usr/bin/python3`; las pruebas de las apps gráficas necesitan PyGObject/GTK4 disponibles:

```bash
(cd components/ally-power && PYTHONPATH=src:packaging:. python3 -m unittest discover -s tests -v)
(cd components/ally-power-decky && python3 -m unittest discover -s tests -v)
(cd components/ally-power-decky && node --test tests/test_live_queue.mjs tests/test_steam_tdp.mjs)
(cd components/ally-rgb && python3 -m unittest discover -s tests -v)
(cd components/ally-rgb && node --test tests/test_queue.mjs tests/test_ui.mjs)
(cd components/bluetooth-trust-manager && python3 -m unittest -v test_installer)
(cd components/bluetooth-trust-manager/payload && python3 -m unittest -v test_app)
```

Las fuentes extraídas del centralizado incluyen `build.py` y todas las piezas. Las fuentes del individual solo contienen su componente: para reconstruir los siete paquetes necesitas el checkout completo o extraer el centralizado.

## Publicación en GitHub

`publish.py` requiere GitHub CLI oficial autenticada y una elección explícita de visibilidad. No se publica nada durante `build.py` ni durante las pruebas.

```bash
gh auth login --hostname github.com --git-protocol https --web
python3 publish.py --owner TU_USUARIO --visibility public
# O --visibility private: nunca se asume público por defecto.
```

Debe ejecutarse sobre un checkout limpio, revisado y con commit en `main`. Comprueba los siete paquetes, crea `SteamOS-ASUS-ROG-ALLY` si no existe, conserva un `origin` ajeno sin modificarlo, empuja sin force y crea `v1.0.0` con los siete ZIP y `SHA256SUMS`. No imprime tokens, no modifica la configuración global de git y no reemplaza una release existente. Descarga de nuevo los ocho assets publicados y comprueba que sus hashes coincidan con los locales. Crear el repositorio exige permisos de GitHub adicionales a los de un conector que solo lee/escribe código en repositorios ya existentes.


## Sustitución de paquetes conservando nombres

Para renovar únicamente los tres paquetes Ally Power/centralizado conservando los
otros tres ZIP existentes, reconstruye primero sus payloads fijados y hashes, y usa:

```bash
python3 build.py --only central ally-power ally-power-decky
python3 verify_packages.py
(cd release && sha256sum -c SHA256SUMS)
```

`--only` requiere los demás ZIP ya presentes para conservar la lista SHA256SUMS
completa. El nombre exterior Decky sigue siendo `Ally-Power-Decky-1.1.0.zip`, pero
el catálogo y el ZIP nativo del interior son 1.1.2. El `.run` de escritorio mantiene
1.0.0 e incorpora el registro de topología CPU propio del equipo destino.

Para una sustitución expresamente autorizada de assets de `v1.0.0`, no ejecutes
`publish.py` (su política normal es rechazar una release existente). Tras revisar y
empujar el commit a main, `gh release upload v1.0.0 --clobber` permite sustituir
solo los tres ZIP revisados y SHA256SUMS. Conserva los restantes assets, tag,
título, descripción y publicación original; no crees una release ni una discusión.
Descarga de nuevo todos los assets y compara bytes y hashes antes de darla por terminada.

## Construir únicamente centralizado y ALLY RGB

```bash
python3 build.py --only central ally-rgb
python3 verify_packages.py
(cd release && sha256sum -c SHA256SUMS)
```

Conserva los cinco individuales existentes byte a byte; el resultado contiene siete ZIP.
Para una sustitución autorizada de la release existente se reemplazan únicamente el
centralizado y SHA256SUMS y se incorpora ALLY-RGB-1.0.0.zip. Su descripción puede incluir
el catálogo completo, sin notas de actualización ni release nueva. Conserva tag, título,
fechas de creación/publicación y destino originales; no fuerces un retag ni un push.
