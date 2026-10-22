# Ally Power 1.0.0 — instalador para SteamOS

Control de TDP, SMT, núcleos e hilos en el **modo escritorio** de ROG Ally.
Paquete offline, sin Decky ni PowerTools. No es software oficial de ASUS o Valve.

## Instalación fácil

1. Copia **Ally-Power-1.0.0-SteamOS-x86_64.run** a la otra Ally y entra en modo escritorio.
2. En Dolphin: botón derecho → Propiedades → Permisos → **Es ejecutable** (si no está marcado).
3. Doble clic → **Ejecutar**. Acepta la instalación e introduce la contraseña de administrador
   **solo en la ventana de autorización del sistema**. Si aún no tienes contraseña, configúrala
   desde la configuración de usuarios de KDE o con `passwd` en Konsole.
4. Busca **Ally Power** en el menú de aplicaciones. El primer **Aplicar** pedirá autorización.

Si Dolphin abre el archivo como texto, abre Konsole en su carpeta y ejecuta:

```sh
bash ./Ally-Power-1.0.0-SteamOS-x86_64.run
```

No ejecutes el instalador con `sudo`: él pide la autorización necesaria. La instalación no
cambia TDP/SMT/núcleos, no instala servicios de inicio ni altera Gaming Mode.

## Compatibilidad y requisitos

- SteamOS x86_64 con escritorio KDE Plasma 6.
- Filtro de hardware: **ROG Ally RC71L** (Z1 o Z1 Extreme) y **ROG Ally X RC72LA** (Z1 Extreme).
- No admite ROG Xbox Ally/Z2 ni otras APUs; no fuerza modelos desconocidos.
- Dependencias del sistema: Python 3, `python-gobject`, `gtk4`, `gdk-pixbuf2`, `pciutils`/libpci,
  polkit/`pkexec`, KDE y `kbuildsycoca6`. Se comprueban antes de instalar.
- El instalador no descarga dependencias ni ejecuta `pacman`; si faltan, se detiene e indica cuáles.
  No se promete compatibilidad con cualquier versión modificada o antigua de SteamOS.
- RyzenAdj **0.19.0** oficial para Linux x86_64 va incluido, con checksum y fuentes/licencias.

**Alcance de las pruebas:** la app original se usó en una RC71L Z1 Extreme con SteamOS 3.8.28.
El empaquetado, sus requisitos, instalación/actualización/desinstalación en directorios aislados,
integridad y pruebas de lógica/interfaz se verifican en ese equipo. Este paquete incorpora un
RyzenAdj oficial más reciente que el 0.14.0 de la instalación original. No se han hecho escrituras
de potencia con ese binario nuevo al empaquetar, ni pruebas físicas en Z1 no Extreme/Ally X.
Que el instalador acepte un modelo no equivale a una certificación de funcionamiento en él.

## Uso

- TDP: **3–25 W en batería**, **3–30 W conectado**. Los valores muy bajos pueden causar lentitud.
- Panel de TDP configurado y núcleos/hilos activos. Los controles muestran cambios pendientes
  hasta pulsar **Aplicar**.
- **Cerrar y conservar** deja los ajustes aplicados y sale. No aplica cambios pendientes.
- **Dejar en la bandeja** mantiene el control y la reducción automática a 25 W al desenchufar.
  Después de salir completamente ya no existe esa vigilancia automática.
- **Restaurar inicial** recupera el estado registrado al comenzar el control. Una interrupción
  inesperada o pérdida de comunicación intenta restaurarlo como protección.
- Lanzador y barra: `icon-gaming.png`. Bandeja: `icon.svg`.
- No coordines simultáneamente ajustes con PowerTools u otro gestor de potencia.

### TDP configurado no significa consumo medido

En algunos SteamOS, RyzenAdj no puede leer la telemetría por las restricciones de memoria.
En ese caso se exige confirmación de los tres comandos de ajuste y se indica **último TDP
aceptado**, no una medición. El punto inicial proviene del último registro válido del mismo
arranque o de los valores ASUS `asus-armoury`. Si ninguno está disponible, el ayudante falla
con un mensaje y no ajusta el hardware. No se deshabilitan protecciones del kernel.

Los registros pueden quedar desfasados si otro controlador modifica directamente la APU.
Reiniciar, cambiar de modo, firmware u otro gestor pueden sustituir el TDP conservado al cerrar.
No existe reaplicación automática al arrancar. No se garantiza el consumo sostenido exacto
ni se alteran voltajes, ventiladores o protecciones térmicas.

## Qué instala y cómo lo quita

- Programa/ayudante y RyzenAdj, propiedad de root: `/usr/local/lib/desktop-power/`.
- Comandos: `/usr/local/bin/ally-power` y `/usr/local/libexec/desktop-power-helper`.
- Lanzadores del usuario: `~/.local/share/applications/local.AllyPower*.desktop`.
- Registro volátil: `/run/desktop-power/last-limits.json`, desaparece al reiniciar.
- No se copia la carpeta privada del creador, historiales, pruebas de migración o credenciales.

Si el sistema está en solo lectura, el instalador lo desactiva temporalmente tras avisar y
restaura su estado al terminar, también si la instalación falla normalmente. Un corte de luz
o terminación forzada durante ese intervalo no permite ejecutar esa restauración: comprueba
`steamos-readonly status` después. Las actualizaciones de SteamOS **pueden borrar /usr/local**;
conserva el `.run` para reinstalar. No se añade un servicio que eluda las actualizaciones del SO.

Para actualizar: cierra la app, incluida la bandeja, y ejecuta el instalador de nuevo. Se guarda
una copia del programa anterior en `/usr/local/lib/desktop-power.backup-*` y del lanzador junto
al `.desktop`. No se elimina la antigua carpeta personal de la app si existía.

Para desinstalar: menú KDE → **Desinstalar Ally Power**, o ejecuta el `.run --uninstall`.
Los archivos instalados se trasladan a `/usr/local/lib/desktop-power.removed-*` para recuperación;
los lanzadores gestionados se quitan después de copiarlos. No se limpian automáticamente estas
copias ni archivos personales. Tampoco se cambia el TDP durante la desinstalación.

## Diagnóstico sin instalar

```sh
bash ./Ally-Power-1.0.0-SteamOS-x86_64.run --check
bash ./Ally-Power-1.0.0-SteamOS-x86_64.run --extract ./AllyPower-extraido
sha256sum -c SHA256SUMS
```

La carpeta de extracción debe ser nueva. La alternativa `.tar.gz` contiene lo mismo;
tras extraerla, `python3 installer.py` inicia el instalador. El SHA256 detecta corrupción,
no autentica al autor: recibe el paquete de una fuente de confianza y no aceptes un instalador
modificado. Se incluyen el código y pruebas para auditarlo.

Consulta `THIRD-PARTY.md` y `licenses/` para dependencias y licencias.
