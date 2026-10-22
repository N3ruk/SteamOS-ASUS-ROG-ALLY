# Reglas del proyecto

- No probar cambios de TDP/SMT, cambio de sesión ni arranque sobre el host real: usar mocks y hogares temporales.
- No instalar/activar Decky automáticamente; exigir instalado y activo para ofrecer el componente.
- Mantener TDP y CPU/SMT independientes y compartir exclusión entre escritorio/Decky.
- Preservar originales de lanzadores, no escribir `/usr/share`, no sobreescribir modificaciones manuales.
- No introducir tokens, credenciales, historiales, `.reference`, backups o `node_modules`.
- Los instaladores en `payloads/` están fijados: modificar sus fuentes exige reconstruirlos explícitamente y regenerar manifests/checksums.
- Verificar `python3 -m unittest discover -s tests -v`, construir seis ZIP y comprobar cada uno en temporal antes de publicar.
- No convertir pruebas simuladas en afirmaciones de validación física.
