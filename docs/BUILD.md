# Construcción y pruebas

## Fuente del proyecto

El repositorio incluye fuentes de las cinco piezas, recursos, pruebas, instaladores originales fijados y fuentes/licencias correspondientes de RyzenAdj. No se incluyen `node_modules`, credenciales, referencias de diagnóstico ni copias de tu equipo. Los binarios oficiales incorporados conservan sus avisos; no se descargan al instalar.

## Generar los seis ZIP

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

`release/` contiene centralizado, cinco individuales y `SHA256SUMS`. Cada ZIP incluye un `.run` autoextraíble sin dependencias de la carpeta original. Fechas y orden de archivos del paquete son fijos para obtener bytes iguales a partir de las mismas fuentes y entradas. La integridad SHA256 comprueba corrupción, no identidad criptográfica del autor.

## Reconstruir aplicaciones

El build central empaqueta los instaladores originales fijados en `payloads/`; editar `components/` por sí solo **no cambia esos binarios**. Para modificarlos:

- Escritorio: `cd components/ally-power; python3 build.py`; copiar su `.run` desde `dist/` a `payloads/` y actualizar versión/nombre en `engine.py` y `build.py` si cambia. Ver `REBUILD.md`.
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
(cd components/bluetooth-trust-manager && python3 -m unittest -v test_installer)
(cd components/bluetooth-trust-manager/payload && python3 -m unittest -v test_app)
```

Las fuentes extraídas del centralizado incluyen `build.py` y todas las piezas. Las fuentes del individual solo contienen su componente: para reconstruir los seis paquetes necesitas el checkout completo o extraer el centralizado.

## Publicación en GitHub

`publish.py` requiere GitHub CLI oficial autenticada y una elección explícita de visibilidad. No se publica nada durante `build.py` ni durante las pruebas.

```bash
gh auth login --hostname github.com --git-protocol https --web
python3 publish.py --owner TU_USUARIO --visibility public
# O --visibility private: nunca se asume público por defecto.
```

Debe ejecutarse sobre un checkout limpio, revisado y con commit en `main`. Comprueba los seis paquetes, crea `SteamOS-ASUS-ROG-ALLY` si no existe, conserva un `origin` ajeno sin modificarlo, empuja sin force y crea `v1.0.0` con los seis ZIP y `SHA256SUMS`. No imprime tokens, no modifica la configuración global de git y no reemplaza una release existente. Descarga de nuevo los siete assets publicados y comprueba que sus hashes coincidan con los locales. Crear el repositorio exige permisos de GitHub adicionales a los de un conector que solo lee/escribe código en repositorios ya existentes.
