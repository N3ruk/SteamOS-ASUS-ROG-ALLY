# SteamOS ASUS ROG ALLY

Instalador **centralizado y opcional**, con cinco componentes independientes, documentación y paquetes individuales. No instala OpenClaw ni depende de él.

## Descargar e instalar

En la release hay **seis ZIP**: uno centralizado y uno por componente. Cada ZIP incluye un instalador `.run` autónomo con código fuente, licencias y documentación dentro.

1. En modo escritorio, extrae el ZIP.
2. Si hace falta, marca el `.run` como ejecutable en **Propiedades → Permisos**.
3. Ejecuta el `.run` **con tu usuario normal, sin sudo**.
4. Lee las explicaciones, marca únicamente los componentes que quieras y pulsa **Instalar seleccionados**. Todo empieza desmarcado.

El centralizado no cambia el arranque, TDP, SMT ni dispositivos Bluetooth durante la instalación. Los instaladores propios de Ally Power y Bluetooth conservan sus confirmaciones; Ally Power pide autorización del sistema.

## Componentes

| Componente | Para qué sirve | Administrador | Compatibilidad |
|---|---|---|---|
| [Volver al modo Gaming](docs/return-gaming.md) | Nuevo icono y confirmación antes de cerrar escritorio | No | SteamOS KDE con `steamosctl` |
| [Alternar arranque](docs/default-mode.md) | Escritorio/Gaming como modo predeterminado del próximo arranque | No | SteamOS con `steamosctl` |
| [Ally Power Escritorio](docs/ally-power.md) | TDP, SMT, núcleos e hilos | Sí, instalación y helper | Ally/Ally X Z1/Z1 Extreme |
| [Ally Power Decky](docs/ally-power-decky.md) | Los mismos dominios de hardware desde Gaming, en tiempo real | API de Decky existente | Ally compatible y Decky instalado **y activo** |
| [Confianza Bluetooth](docs/bluetooth-trust-manager.md) | Retirar confianza sin borrar emparejamientos; útil con mandos PS3 | No | SteamOS KDE con BlueZ y GTK4 |

**Los controles de potencia no son universales**: se limitan a RC71L/RC72LA, AMD Ryzen Z1/Z1 Extreme y SteamOS x86_64. Los demás componentes no requieren un modelo Ally. No se promete compatibilidad con cualquier versión antigua o futura de SteamOS.

## Decisiones de diseño

- Ningún componente seleccionado inicialmente; sin instalaciones ni descargas ocultas.
- Decky solo se ofrece si el servicio de Loader está instalado y activo y sus requisitos se cumplen. No se instala ni activa Decky por detrás.
- Los originales de los lanzadores, incluidos enlaces simbólicos, se guardan antes de sustituirlos. No se escribe en `/usr/share/applications`.
- Escritorio y Decky comparten exclusión de hardware; no se detienen otros gestores. Detección de procesos y bloqueo no garantizan detectar firmware ni gestores desconocidos.
- En Decky, **«TDP de Steam desactivado»** aparece primero tras «Ajuste manual»: habilita únicamente TDP del plugin. SMT/CPU no dependen de ese interruptor. Cambios en tiempo real, sin botones Aplicar, Liberar ni Restaurar.
- Se verifica SHA256 antes de invocar cada paquete. Esto detecta daños; no es una firma de autor.
- No se recopila telemetría ni se envían dispositivos/configuraciones a internet. La integración Decky utiliza solo `127.0.0.1:1337`, con token en memoria.

## Comprobar sin instalar

```bash
bash SteamOS-ASUS-ROG-ALLY-1.0.0-SteamOS.run --check
bash SteamOS-ASUS-ROG-ALLY-1.0.0-SteamOS.run --verify
bash SteamOS-ASUS-ROG-ALLY-1.0.0-SteamOS.run --extract fuentes
```

`--check` enumera disponibles/no disponibles, no inicia apps ni toca hardware. Devuelve 0 si al menos un componente es elegible, 1 si ninguno lo es o hay un error de integridad. `--verify` solo comprueba integridad.

## Documentación y código

- [Instalación, actualización y recuperación](docs/INSTALLATION.md)
- [Compilar y generar los seis paquetes](docs/BUILD.md)
- [Pruebas y límites de verificación](docs/VERIFICATION.md)
- [Notas de la release](docs/RELEASE.md)
- [`installer/`](installer): selección, comprobaciones, transacciones y adaptador Decky.
- [`components/`](components): fuentes originales de cada aplicación, instaladores y recursos.

Código propio bajo MIT; **no** se aplica esa licencia a todo el contenido indiscriminadamente. RyzenAdj y recursos de terceros conservan sus licencias; los iconos PNG aportados por el usuario no se relicencian como MIT. Véase [THIRD-PARTY.md](THIRD-PARTY.md).

Los nombres de descarga de la distribución 1.0.0 se conservan. El individual
`Ally-Power-Decky-1.1.0.zip` contiene el plugin nativo 1.1.2; consulta el catálogo
y SHA256SUMS del contenido, no deduzcas la versión interna del nombre exterior.
