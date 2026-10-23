# Verificación 1.0.0

- TypeScript estricto, Rollup, 46 pruebas Python y 12 JavaScript correctos.
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
- No se escriben TDP, SMT, ventiladores, EC ni MCU; no depende de termios/serial/HID.

Las pruebas usan dispositivos temporales y no acreditan el color físico de los LED.
La comprobación de carga real y persistencia del backend se realiza por separado, sin
reiniciar ni suspender físicamente la máquina y sin aplicar patrones RGB de prueba.
