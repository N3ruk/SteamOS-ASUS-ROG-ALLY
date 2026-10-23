# Reglas del proyecto

- No probar cambios de TDP/SMT, cambio de sesión ni arranque sobre el host real: usar mocks y hogares temporales.
- No instalar/activar Decky automáticamente; exigir instalado y activo para ofrecer el componente.
- Mantener TDP y CPU/SMT independientes y compartir exclusión entre escritorio/Decky.
- Preservar originales de lanzadores, no escribir `/usr/share`, no sobreescribir modificaciones manuales.
- No introducir tokens, credenciales, historiales, `.reference`, backups o `node_modules`.
- Los instaladores en `payloads/` están fijados: modificar sus fuentes exige reconstruirlos explícitamente y regenerar manifests/checksums.
- Verificar `python3 -m unittest discover -s tests -v`, construir siete ZIP y comprobar cada uno en temporal antes de publicar.
- No convertir pruebas simuladas en afirmaciones de validación física.

- ALLY RGB es RGB solo: preservar efectos/colores/velocidades independientes, selección de editor sin escrituras y recuperación optativa. Su versión de distribución es 1.0.0. No reinstalarlo en el host mientras esté activo para comprobar embalaje.
- Para refrescar solo centralizado y RGB, usar `build.py --only central ally-rgb`, conservar los cinco individuales previos y verificar los siete paquetes.

- ALLY RGB debe leer únicamente batería interna de sistema (BAT0/BATn); nunca sustituirla por una batería de mando/periférico al faltar datos. Mantener pruebas con porcentajes distintos.
