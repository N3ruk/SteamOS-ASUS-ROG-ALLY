# Reconstruir

Requiere Python 3; para pruebas gráficas, las dependencias del LEEME.
Desde una copia de los fuentes con estructura `src/`, `tests/`, `packaging/`, `licenses/`:

1. Copia `LEEME.md`, `THIRD-PARTY.md` y `licenses/` desde la raíz del paquete a esta carpeta.
2. Crea `vendor/` y copia allí `RyzenAdj-v0.19.0-source.tar.gz`.
3. Descarga el binario oficial de la URL en THIRD-PARTY a
   `vendor/ryzenadj-manylinux_2_28-x86_64.tar.gz`.
4. `python3 build.py` verifica los hashes fijados y crea los dos artefactos en `dist/`.
5. `PYTHONPATH=src:packaging:. python3 -m unittest discover -s tests -v`

El constructor usa una lista explícita de archivos; no empaqueta el home ni las copias de
seguridad. No instala nada ni modifica el hardware. Para usar RyzenAdj recompilado, consulta
su README y CMake en las fuentes completas incluidas; cambia el archivo proveedor y su hash
en `build.py`, dejando constancia de los cambios al redistribuirlo. No hay firma digital.
