# Verificación 1.2

- TypeScript estricto, Rollup, 124 pruebas Python y 18 JavaScript correctos.
- Cuatro efectos distintos compuestos a la vez; cambiar selección no cambia el frame.
- Editar otra zona mantiene el tiempo de las ya activas y conserva un único trabajador.
- Selección pura sin escrituras, bloqueo ni reinicio de tiempos; en inicio vacío tampoco
  crea configuración ni activa recuperación por defecto.
- Cambios de metadatos (selección/recuperación) sin reiniciar ni escribir iluminación.
- Configuración multiefecto completa conservada al suspender/reanudar y recrear el gestor.
- Interfaz con hooks/Decky simulados: selector muestra el efecto propio, grupo mixto no
  iguala efectos, edición seguida de cambio de zona no se pierde en la cola.
- Transición con dos colores por zona, color RGB por canal sin alterar zonas no seleccionadas.
- Validación de cuatro configuraciones individuales y migración de esquemas de desarrollo anteriores.
- Se mantienen pruebas de exclusión, cambios externos, pérdida de dispositivo, rollback,
  límites de color/brillo, guardado atómico, corrupción, recuperación optativa y apagado.
- Batería interna frente a mando detectado primero, BAT0 sin scope, scope Device/System,
  0%, datos inválidos/ausentes/inaccesibles y desconexión de la batería interna; nunca
  se usa la de un periférico. Interfaz con «batería sin datos» si no hay lectura válida.
- No se escriben TDP, SMT, ventiladores, EC, firmware ni configuración del mando;
  no depende de termios/serial/bibliotecas HID externas.
- Fallback RGB para kernel que recorta colores: pruebas de serialización de cuatro
  zonas, dimmer, selector estricto de interfaz y descriptor, identidad del fd,
  lista positiva de dos comandos, rechazo de otras órdenes y padding no nulo,
  ausencia de envíos al consultar, cierre ante fallo y detección de cambio sysfs.
- Se mantiene sysfs/readback en kernels compatibles. HID declara únicamente
  aceptación por transporte; no inventa lectura física ni rollback.

## Candidata local session-scope-v2

- Relojes simulados: espera de pulsos, 10 s continuos, huecos que reinician la cuenta,
  timeout de preparación, suspensión real frente a bloqueo del event loop, pulsos
  duplicados y un solo envío directo (sin brillo cero temporal).
- Edición/desactivación/cierre ganan a recuperación pendiente; fallo no se reintenta.
- Perfil fijo sin trabajador/flock/lecturas periódicas; get_state solo caché.
- Animador se detiene al congelarse sin matar el auxiliar en la transición.
- Scope verificado, inscripción antes de payload, fracaso cerrado y rechazo de comandos
  de un ciclo de sueño anterior. Lecturas/escrituras reales solo en user.slice.
- Timeout de lectura pausado mientras está congelado; auxiliar no terminable bloquea
  sustitución. Guard EOF Decky conservado.
- Todas las pruebas de hardware usan dispositivos temporales, no los LED del equipo.

Comprobado en el host: instalación nativa 1.2, probe sin acceso LED dentro de
user.slice, scopes recogidos al salir y una restauración directa al activar la opción
tras 10 s; perfil conservado salvo resume=true. POWER y Loader no reiniciados.
La respuesta de StartTransientUnit es un trabajo asíncrono: se espera y verifica
el traslado efectivo del PID antes de enviar cualquier payload.

El usuario confirma tres suspensiones/reanudaciones correctas con un emulador abierto y
recuperación activa. No demuestra una causa concreta de kernel ni todos los casos.

Nuevas parejas 2–3 y 1–4 comprobadas en selección, edición y persistencia; edición
RGB/efecto/velocidad solo afecta al grupo. Porcentajes visibles RGB y transición
(0–255 → 0–100 %) y velocidad (mínimo10 → 0 %, máximo100 → 100 %), sin cambiar
configuración ni precisión. Recuperación session-scope-v2 sin modificaciones.
El usuario valida también la interfaz real de las nuevas parejas y porcentajes.
Los resultados corresponden a esta RC71L y no prueban compatibilidad universal.
