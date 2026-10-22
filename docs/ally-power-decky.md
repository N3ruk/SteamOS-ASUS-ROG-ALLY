# Ally Power — Decky Gaming 1.1.0

Control de TDP, SMT, núcleos e hilos desde el panel de Decky en modo Gaming. Requiere hardware compatible con Ally Power y **Decky Loader instalado y activo**. No instala Loader, no lo activa y no modifica Steam al instalar.

## Interfaz y control

El primer control bajo **«Ajuste manual»** es **«TDP de Steam desactivado»**. Activarlo desactiva realmente el control TDP nativo mediante la interfaz interna de Steam y, tras verificarlo, habilita el TDP del plugin. Si no está activo se usa el control TDP nativo de Steam. Si la API de Steam cambia o no funciona, el TDP del plugin no se habilita.

**SMT/CPU son independientes** de ese interruptor. Los cambios se serializan y aplican en tiempo real; no hay botones Aplicar, Liberar ni Restaurar. Si Steam reactiva el control nativo por un perfil, el plugin cede TDP en vez de combatirlo.

No modifica hardware al cargar o consultar estado. Solo toma el bloqueo compartido cuando se solicita una operación; detecta gestores conocidos y rechaza competir. Salir de Gaming hace que ceda sin restaurar encima de otro gestor. Los límites mostrados son configuración conocida, no una medición del consumo real.

## Instalar / actualizar / quitar

Paquete individual: `Ally-Power-Decky-1.1.0.zip`. Contiene instalador `.run` y dentro el **ZIP nativo Decky**, fuentes y licencias. La API local de Decky se verificó con Loader 3.3.0. Se requiere `python3-aiohttp` del sistema; no se instala automáticamente. La instalación oficial/manual desde ZIP en Decky sigue siendo una alternativa si cambia su API local.

Se verifica hash del ZIP, autorización local en memoria, solicitud de instalación exacta, versión registrada y respuesta del backend. No se imprime el token ni se reinicia Steam. Antes de actualizar una versión existente se comprueba que no controle hardware y se guarda un ZIP de la instalación; véase [recuperación](INSTALLATION.md).

Para desinstalar usa los ajustes de plugins de Decky. Para restaurar una copia anterior, instálala con el mecanismo ZIP de Decky después de dejar de controlar el hardware. El centralizado no añade botones de control a la interfaz del plugin.

## Fuentes y estado de pruebas

[`components/ally-power-decky`](../components/ally-power-decky), [README original](../components/ally-power-decky/README.md), [historial de verificación](../components/ally-power-decky/VERIFICACION.md). Código MIT propio y fuentes/licencias de RyzenAdj incluidas.

TypeScript, compilación y pruebas simuladas verifican lógica y exclusión; no prueban interacción física en Gaming ni escrituras reales sobre otra Ally. Véase [verificación de la suite](VERIFICATION.md).
