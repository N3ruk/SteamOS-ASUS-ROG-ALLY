# ALLY RGB

- No escribir TDP/SMT, ventiladores, EC, firmware ni configuración del mando. Se permiten atributos RGB fijos del kernel y, por autorización expresa del usuario del 24/10/2026, un fallback hidraw exclusivamente RGB en RC71L cuando el kernel recorta colores empaquetados. Solo informes fijos de color de cuatro zonas y brillo LED, identidad USB/interfaz/dispositivo ligada al LED, sin API de paquetes arbitrarios, detach del driver ni comandos de persistencia/firmware.
- En HID, el éxito del transporte no es lectura física del color. Declararlo como tal y detectar cambios del estado sysfs observado; no fingir readback ni protección universal ante escritores HID desconocidos.
- Pruebas con dispositivos temporales; nunca usar luces reales como pruebas unitarias.
- get_state es solo lectura. Al iniciar, restaurar únicamente la última configuración guardada con resume=true, por petición explícita del usuario. Sin configuración válida no escribir ni adquirir bloqueo.
- Zonas selecciona solo lo que se edita: nunca debe congelar, detener ni reiniciar otras zonas. Cada zona conserva efecto, velocidad, color, transición y tiempo propios; se componen en un solo trabajador y frame RGB.
- La selección pura no escribe LED ni adquiere control. Los cambios coalescidos deben conservar ediciones anteriores aunque se cambie de selector antes de enviarlas.
- No añadir perfiles, colores rápidos ni botones de convivencia a la interfaz simplificada.
- No desactivar HueSync ni otros gestores sin petición específica.
- Cola serializada, límites de frecuencia y cierre sin restaurar sobre otros escritores.
- No publicar GitHub ni modificar la suite sin petición.

## Operación local de Decky

- WSRouter mantiene un solo socket: abrir un cliente externo puede cerrar el de Steam y perder eventos frontend (como unload). Con Steam conectado, preferir la API de frontend existente vía CDP, sin imprimir tokens; la conexión API init 2 para ALLY RGB ofrece callable. Verificar backend y registro frontend por separado.
- La actualización y loader/reload_plugin pueden terminar en el servidor aunque un cliente reciba cierre de websocket; inspeccionar estado antes de repetir una mutación.
- El frontend no debe liberar un backend nuevo desde un onDismount tardío. La liberación pertenece a _unload del backend; cerrar panel conserva efectos.

- Batería del equipo: BAT0/BATn de sistema; no elegir el primer power_supply Battery. Excluir scope Device, admitir BAT0 sin scope y devolver None ante ausencia/lectura no válida. Porcentaje y efecto Batería deben usar el mismo lector.

- Candidata local `session-scope-v2` (mantiene versión 1.2): no suscribirse a logind,
  no monitores de reloj ni sondeo RGB en reposo. El frontend global solo envía pulsos;
  el backend comprueba BOOTTIME/MONOTONIC y cuenta 10 s de continuidad, una aplicación
  directa sin apagado/encendido y sin reintentos. No depende de abrir QAM.
- get_state usa caché, nunca auxiliares/lecturas RGB. Perfiles fijos liberan trabajador
  y flock. Solo los efectos dinámicos mantienen un auxiliar, sin sondeo de LED.
- Toda E/S real debe ocurrir dentro de un scope transitorio `ally-rgb-io-*.scope` en
  user.slice, verificado por padre e hijo antes de enviar/aceptar comandos. No añadir
  servicios persistentes, hooks de sueño, inhibidores ni cambiar el freezer.
- Comprobar ciclo de sueño por operación/informe; rechazar comandos antiguos. No matar
  auxiliares congelados ni sustituir uno no terminable: conserva flock. Cierre acotado.
- El usuario confirmó tres suspensiones correctas con un emulador y recuperación activa.
  La interfaz de parejas/porcentajes también ha sido validada explícitamente.
  Para futuras modificaciones respetar las condiciones de validación del usuario. Mantener versión/nombres/tag/release1.2;
  actualizar main y assets silenciosamente. Por petición nueva, SÍ actualizar la
  descripción del mismo release con arquitectura real y funciones; título intacto,
  sin release nuevo ni anuncio adicional. Ante fallo, investigar e iterar.
- Porcentajes RGB solo de presentación (0–255 → 0–100 %); conservar precisión del
  color y configuración. Velocidad: mínimo interno10 equivale0 %, máximo100 a100 %;
  no cambiar el ritmo/valores guardados por una petición de indicador visual.
