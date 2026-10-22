# Verificación y límites

## Suite 1.0.0

27 pruebas propias superadas; además, reejecutadas 21 de Ally Power, 13 de Bluetooth y 43 de Decky (35 Python + 8 JavaScript). Los números se refieren a pruebas automatizadas, no a equipos físicos.

La interfaz gráfica se prueba con casillas desmarcadas y sin ofrecer Decky inactivo.

Se prueban con hogares temporales y servicios simulados: instalación sin cambios de arranque/hardware, ruta con espacios, preservación de archivos/enlaces originales, reinstalación, desinstalación, rechazo de archivos modificados y de directorios enlazados, rollback ante fallo, exclusión de operaciones, integridad y rutas de manifiesto, Decky instalado/activo, petición correcta y rechazo de confirmaciones equivocadas.

Los seis ZIP se extraen en directorios temporales, se verifica su `.run` y su manifiesto, la lista correcta de componentes y la presencia de fuentes/licencias. El comprobador central se ejecuta en la Ally sin instalar ni cambiar ajustes. No se ejecutan los scripts de cambio de sesión o arranque sobre el equipo real para probarlos.

## Aplicaciones incluidas

Historial de las versiones originales: Ally Power escritorio 21 pruebas, Confianza Bluetooth 13 pruebas, Decky 35 Python + 8 JavaScript. La app Bluetooth fue probada manualmente por el usuario; el panel Decky 1.1.0 requiere aún prueba de interacción física en Gaming. La suma de pruebas no representa dispositivos físicamente validados.

La instalación del centralizado sobre un sistema nuevo y otras Ally/Ally X todavía requiere verificación física. Los tests aislados no acreditan compatibilidad universal con todas las versiones de SteamOS, Decky o del cliente Steam. La integración TDP de Steam usa una interfaz interna susceptible de cambiar.

El instalador no resuelve dependencias modificando el sistema. Si faltan, el componente queda no disponible con explicación. Ninguna prueba de empaquetado cambia tus ajustes de TDP, SMT, Bluetooth o arranque.

## Ajustes de distribución sin cambio funcional

Se sustituyeron identificadores de dispositivo de los fixtures de pruebas Bluetooth por una dirección ficticia local. Se conservaron los textos de licencia npm en el plugin y se regeneraron ambos paquetes afectados. No cambió el código funcional de las aplicaciones originales.
