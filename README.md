# SteamOS ASUS ROG ALLY 1.3

Instalador **centralizado y opcional**, con siete componentes independientes, documentación y paquetes individuales. No instala OpenClaw ni depende de él.

## Descargar e instalar

En la [release 1.3](https://github.com/N3ruk/SteamOS-ASUS-ROG-ALLY/releases/tag/v1.3) hay **ocho ZIP**: uno centralizado y uno por componente. Cada ZIP incluye un instalador `.run` autónomo con código fuente, licencias y documentación dentro.

1. En modo escritorio, extrae el ZIP.
2. Si hace falta, marca el `.run` como ejecutable en **Propiedades → Permisos**.
3. Ejecuta el `.run` **con tu usuario normal, sin sudo**.
4. Lee las explicaciones, marca únicamente los componentes que quieras y pulsa **Instalar seleccionados**. Todo empieza desmarcado.

El centralizado no cambia el arranque, TDP, SMT ni dispositivos Bluetooth durante la instalación. Los instaladores propios de Ally Power y Bluetooth conservan sus confirmaciones; Ally Power pide autorización del sistema.

La colección pasa a **1.3** por incorporar **Video Output ALLY for DOCKs 1.0**.
Los demás componentes conservan sus versiones y paquetes.

## Componentes

| Componente | Para qué sirve | Administrador | Compatibilidad |
|---|---|---|---|
| [Volver al modo Gaming](docs/return-gaming.md) | Nuevo icono y confirmación antes de cerrar escritorio | No | SteamOS KDE con `steamosctl` |
| [Alternar arranque](docs/default-mode.md) | Escritorio/Gaming como modo predeterminado del próximo arranque | No | SteamOS con `steamosctl` |
| [Ally Power Escritorio](docs/ally-power.md) | TDP, SMT, núcleos e hilos | Sí, instalación y helper | Ally/Ally X Z1/Z1 Extreme |
| [Ally Power Decky](docs/ally-power-decky.md) | Los mismos dominios de hardware desde Gaming, en tiempo real | API de Decky existente | Ally compatible y Decky instalado **y activo** |
| [ALLY RGB](docs/ally-rgb.md) | Iluminación: cuatro efectos, colores y velocidades independientes; recuperar al despertar/encender | API de Decky existente | Ally RC71L, kernel RGB compatible y Decky instalado **y activo** |
| [Video Output ALLY for DOCKs](docs/video-output-ally.md) | Elegir pantalla en Gaming, nombres de monitor e interna ASUS ALLY; solo vídeo | API de Decky existente | Ally RC71L, Gamescope/AMDGPU y Decky instalado **y activo** |
| [Confianza Bluetooth](docs/bluetooth-trust-manager.md) | Retirar confianza sin borrar emparejamientos; útil con mandos PS3 | No | SteamOS KDE con BlueZ y GTK4 |

**Los controles de potencia no son universales**: se limitan a RC71L/RC72LA, AMD Ryzen Z1/Z1 Extreme y SteamOS x86_64. ALLY RGB requiere RC71L y la interfaz LED de cuatro zonas; Ally X no está validada. Los lanzadores y Bluetooth no requieren un modelo Ally. No se promete compatibilidad con cualquier versión antigua o futura de SteamOS.

## Decisiones de diseño

- Ningún componente seleccionado inicialmente; sin instalaciones ni descargas ocultas.
- Decky solo se ofrece si el servicio de Loader está instalado y activo y sus requisitos se cumplen. No se instala ni activa Decky por detrás.
- Los originales de los lanzadores, incluidos enlaces simbólicos, se guardan antes de sustituirlos. No se escribe en `/usr/share/applications`.
- Escritorio y Decky comparten exclusión de hardware; no se detienen otros gestores. Detección de procesos y bloqueo no garantizan detectar firmware ni gestores desconocidos.
- En Decky, **«TDP de Steam desactivado»** aparece primero tras «Ajuste manual»: habilita únicamente TDP del plugin. SMT/CPU no dependen de ese interruptor. Cambios en tiempo real, sin botones Aplicar, Liberar ni Restaurar.
- Ally Power prepara la CPU que aún controla antes de suspender. Su recuperación optativa espera 10 segundos de Gaming estable y reaplica una vez TDP y después CPU/SMT; no aplica perfiles al arrancar.
- ALLY RGB controla solo iluminación; elegir otra zona no detiene sus efectos. Puede recuperar ajustes RGB guardados al cargar si el usuario activó esa opción.
- Video Output ALLY for DOCKs conserva el motor de selección/reversión verificada y elimina controles de audio. Se instala desde escritorio y no se sustituye mientras controla pantallas.
- Se verifica SHA256 antes de invocar cada paquete. Esto detecta daños; no es una firma de autor.
- No se recopila telemetría ni se envían dispositivos/configuraciones a internet. La integración Decky utiliza solo `127.0.0.1:1337`, con token en memoria.

## Comprobar sin instalar

```bash
bash SteamOS-ASUS-ROG-ALLY-1.3-SteamOS.run --check
bash SteamOS-ASUS-ROG-ALLY-1.3-SteamOS.run --verify
bash SteamOS-ASUS-ROG-ALLY-1.3-SteamOS.run --extract fuentes
```

`--check` enumera disponibles/no disponibles, no inicia apps ni toca hardware. Devuelve 0 si al menos un componente es elegible, 1 si ninguno lo es o hay un error de integridad. `--verify` solo comprueba integridad.

## Documentación y código

- [Instalación, actualización y recuperación](docs/INSTALLATION.md)
- [Compilar y generar los ocho paquetes](docs/BUILD.md)
- [Pruebas y límites de verificación](docs/VERIFICATION.md)
- [Notas de la release](docs/RELEASE.md)
- [`installer/`](installer): selección, comprobaciones, transacciones y adaptador Decky.
- [`components/`](components): fuentes originales de cada aplicación, instaladores y recursos.

Código propio bajo MIT; **no** se aplica esa licencia a todo el contenido indiscriminadamente. RyzenAdj y recursos de terceros conservan sus licencias; los iconos PNG aportados por el usuario no se relicencian como MIT. Véase [THIRD-PARTY.md](THIRD-PARTY.md).

El centralizado se distribuye como **1.3** por integrar el nuevo plugin de vídeo
**Video Output ALLY for DOCKs 1.0**. POWER y RGB permanecen en **1.2**, con sus
recuperaciones ya documentadas y sin cambios de código o paquetes. El nuevo individual
y el centralizado incorporan el mismo ZIP nativo de vídeo. Los seis individuales
previos conservan sus bytes. Los releases **v1.2 y v1.0.0** siguen disponibles intactos.

Video Output ALLY for DOCKs es un derivado BSD-3-Clause con licencia y créditos
originales; véase [THIRD-PARTY.md](THIRD-PARTY.md). La carga y las pruebas automatizadas
no equivalen a validación física de todos los monitores/docks en Gaming.
