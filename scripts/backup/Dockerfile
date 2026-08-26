# Auditoría de seguridad 2026-08-25 (hallazgo B5): tag + digest -- ver
# nota equivalente en backend/Dockerfile.
FROM postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685

# findutils/coreutils reales -- el `find ... -mtime N -delete` de
# backup_loop.sh y el `date` con formato ISO necesitan comportarse igual
# que en cualquier distro, no como las versiones recortadas de BusyBox
# que trae Alpine por defecto (ej. el `find` de BusyBox no soporta -delete).
RUN apk add --no-cache findutils coreutils

COPY backup_loop.sh restaurar.sh /scripts/
RUN chmod +x /scripts/backup_loop.sh /scripts/restaurar.sh

ENTRYPOINT ["/scripts/backup_loop.sh"]
