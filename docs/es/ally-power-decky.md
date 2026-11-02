# Ally Power — Decky Gaming 1.2

[English](../ally-power-decky.md)

Control de TDP, SMT, núcleos e hilos desde el panel de Decky en modo Gaming. Requiere hardware compatible con Ally Power y **Decky Loader instalado y activo**. No instala Loader, no lo activa y no modifica Steam al instalar.

## Interfaz y control

El primer control bajo **«Ajuste manual»** es **«TDP de Steam desactivado»**. Activarlo desactiva realmente el control TDP nativo mediante la interfaz interna de Steam y, tras verificarlo, habilita el TDP del plugin. Si no está activo se usa el control TDP nativo de Steam. Si la API de Steam cambia o no funciona, el TDP del plugin no se habilita.

**SMT/CPU son independientes** de ese interruptor. Los cambios se serializan y aplican en tiempo real; no hay botones Aplicar, Liberar ni Restaurar. Si Steam reactiva el control nativo por un perfil, el plugin cede TDP en vez de combatirlo.

No modifica hardware al cargar o consultar estado. Solo toma el bloqueo compartido cuando se solicita una operación; detecta gestores conocidos y rechaza competir. Salir de Gaming normaliza antes la CPU que aún posee y cede sin sobrescribir a otro gestor. Los límites mostrados son configuración conocida, no una medición del consumo real.

## Suspensión y recuperación

Antes de reducir CPU/SMT, adquiere una protección logind **delay**, no block. Antes de dormir activa SMT y todos los hilos de la CPU todavía poseída. La preparación no toca TDP, RGB ni controles HID; está acotada y libera siempre su inhibidor. El auxiliar D-Bus solo maneja metadatos: toda E/S CPU/RyzenAdj permanece en un scope temporal verificado de `user.slice`, con comprobaciones de sesión/freezer antes de operar. No hay servicios propios ni hooks persistentes.

**Recuperar ajustes al despertar** es optativo. Recuerda los ajustes propios solo en memoria y espera 10 segundos de pulsos continuos de Steam en Gaming antes de recuperar una vez **TDP→CPU/SMT**. CPU permanece completa durante la espera; se readquiere la protección antes de reducirla. TDP respeta el techo actual de batería/cargador y cede al control nativo si Steam lo retoma o cambia su perfil. Funciona con QAM cerrado.

Huecos de pulsos >4 s reinician la cuenta y el intento caduca a los 60 s. Edición manual, otra suspensión, cambio de juego, salida de Gaming o control competidor cancelan. Si Steam no identifica todavía el juego, espera sin aplicar su configuración al menú. No se reintenta en bucle. Solo persiste el interruptor, no perfiles; al arrancar o recargar no aplica CPU/TDP. Con recuperación apagada mantiene CPU completa al despertar hasta una acción manual.

## Instalar / actualizar / quitar

Paquete individual: `Ally-Power-Decky-1.2.zip`. Contiene instalador `.run` y dentro el **ZIP nativo Decky 1.2**, fuentes y licencias. El ZIP exterior no se instala directamente en Decky: usa el que se encuentra en `payloads/` tras extraer el `.run` con `--extract fuentes`. La API local de Decky se verificó con Loader 3.3.0. Se requiere `python3-aiohttp` del sistema; no se instala automáticamente. La instalación oficial/manual desde ZIP en Decky sigue siendo una alternativa si cambia su API local.

Se verifica hash del ZIP, autorización local en memoria, solicitud de instalación exacta, versión registrada y respuesta del backend. No se imprime el token ni se reinicia Steam. Antes de actualizar una versión existente se comprueba que no controle hardware ni tenga recuperación pendiente y se guarda un ZIP de la instalación; véase [recuperación](INSTALLATION.md).

Para desinstalar usa los ajustes de plugins de Decky. Para restaurar una copia anterior, instálala con el mecanismo ZIP de Decky después de dejar de controlar el hardware. El centralizado no añade botones de control a la interfaz del plugin.

## Fuentes y estado de pruebas

[`components/ally-power-decky`](../../components/ally-power-decky), [README original](../../components/ally-power-decky/README.md), [historial de verificación](../../components/ally-power-decky/VERIFICACION.md). Código MIT propio y fuentes/licencias de RyzenAdj incluidas.

TypeScript, compilación y pruebas simuladas verifican lógica y exclusión; no prueban interacción física en Gaming ni escrituras reales sobre otra Ally. Véase [verificación de la suite](VERIFICATION.md).

115 pruebas Python y 16 JavaScript cubren sesión, preparación, recuperación, cancelaciones e independencia CPU/TDP. El usuario confirmó por separado el funcionamiento real de la preparación y de la recuperación automática en Gaming antes de este refresco. No se extrapola a otras Ally.


## Topología y versión de distribución

El archivo de distribución, su `.run`, el ZIP nativo y el catálogo usan **1.2**.
Incluye el recuadro de estado y Ajuste manual, detección de `gamescope-wl` y
validación estable de núcleos/hilos al alternar SMT.

El plugin guarda solo metadatos físicos verificados en
`/var/lib/ally-power-decky/cpu-topology.json`; no son ajustes de potencia y no se
aplican al arrancar. Esto permite reiniciar el backend con SMT apagado sin depender
de la app de escritorio. También puede usar una instantánea válida de escritorio.
Se rechazan los IDs incompletos/puestos a cero de CPU offline, y nunca se asume que
cada CPU apagada sea un núcleo nuevo. Si no hay ninguna identificación completa ni
instantánea válida, se pide iniciar con todos los núcleos/SMT disponibles: no se
activan CPU para inspeccionarlas ni se distribuye una topología de otro equipo.
