# Ally Power — Escritorio 1.0.0

Control manual de **TDP, SMT, núcleos e hilos** con interfaz de escritorio y bandeja. No requiere PowerTools. El paquete original incluye RyzenAdj 0.19.0 y sus fuentes/licencias.

Compatibilidad comprobada por el instalador: SteamOS x86_64, ASUS ROG Ally RC71L o Ally X RC72LA y AMD Ryzen Z1/Z1 Extreme. La comprobación de modelo no equivale a prueba física en todas las variantes.

## Instalación

Individual: `Ally-Power-Escritorio-1.0.0.zip`, o selección en centralizado. Reutiliza sin alterar `Ally-Power-1.0.0-SteamOS-x86_64.run`. Se pide autorización del sistema, no se almacena tu contraseña. Si está abierta, ciérrala incluida la bandeja. Instala app/helper en `/usr/local`, sin servicios de aplicación permanente. No aplica ajustes al instalar.

El instalador propio comprueba sus dependencias; entre ellas Python/PyGObject GTK4, `pkexec`, `kdialog`, utilidades del sistema y bibliotecas necesarias de RyzenAdj. No se usa pacman para modificar el sistema.

## Uso y convivencia

Abre Ally Power en el menú. Usa los controles de la app y su comportamiento original de Aplicar; **la petición de cambios en tiempo real corresponde al plugin Decky**, no se cambia aquí la app ya existente. El helper autorizado limita las escrituras a CPU/TDP y comparte `/run/desktop-power.lock` con Decky.

No lo uses a la vez que otro gestor de potencia/SMT. El cierre normal conserva los últimos ajustes; una caída del controlador puede restaurar los dominios todavía controlados. Cierra la app antes de usar el plugin en Gaming. No se promete neutralizar gestores externos desconocidos.

## Desinstalar / reconstruir

Desinstalador del menú o `bash Ally-Power-1.0.0-SteamOS-x86_64.run --uninstall`. Conserva copia recuperable. Algunas actualizaciones de SteamOS pueden sustituir `/usr/local`; guarda el instalador para reinstalar.

Fuentes: [`components/ally-power`](../components/ally-power). Guías originales: [LEEME](../components/ally-power/LEEME.md), [REBUILD](../components/ally-power/REBUILD.md), [terceros](../components/ally-power/THIRD-PARTY.md). Código MIT, RyzenAdj LGPL/GPL según sus archivos y fuentes correspondientes; PNG aportado excluido de MIT.
