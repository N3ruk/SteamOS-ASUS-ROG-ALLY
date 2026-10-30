# Verificación 1.2

- TypeScript estricto, Rollup, 108 pruebas Python y 14 JavaScript correctos.
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

- Recuperación backend con señales logind y respaldo BOOTTIME/MONOTONIC; señales duplicadas,
  avisos perdidos, bucle ocupado sin falsa reanudación y cierre del proceso monitor.
- Recuperación única de brillo y frame fijo, disponibilidad tardía antes de escribir,
  fallos sin reintentos de escritura, cancelación por edición/cierre y suspensión repetida.
- No reintenta contra otro gestor, identidad inválida, trigger o bloqueo ocupado.
- Interfaz funcional aunque no existan los hooks internos de suspensión de Steam.

Las pruebas usan dispositivos temporales y no acreditan el color físico de los LED.
La comprobación de carga real y persistencia del backend se realiza por separado, sin
reiniciar ni suspender físicamente la máquina y sin aplicar patrones RGB de prueba.

## 1.2: recuperación diferida

- 108 pruebas Python aprobadas: protocolo HID, identidad, perfiles, fases,
  cancelación por suspensión/edición/cierre, fallos sin reintento y auxiliares
  reales simulados con timeout/flock heredado. No utilizan luces reales como
  dispositivos de prueba.
- TypeScript y Rollup correctos; 14 pruebas JavaScript de cola e interfaz aprobadas.
- Observador D-Bus y entrada de lectura del auxiliar comprobados en el host sin
  enviar informes RGB. La validación del transporte al aplicar no demuestra
  lectura física del color ni valida una suspensión real en Gaming.

- 1.2 añade pruebas del guard EOF local: cesión del bucle, cancelación, mensajes normales, idempotencia y exclusión de versiones con comprobación nativa.
