FROM postgres:16-alpine

# findutils/coreutils reales -- el `find ... -mtime N -delete` de
# backup_loop.sh y el `date` con formato ISO necesitan comportarse igual
# que en cualquier distro, no como las versiones recortadas de BusyBox
# que trae Alpine por defecto (ej. el `find` de BusyBox no soporta -delete).
RUN apk add --no-cache findutils coreutils

COPY backup_loop.sh restaurar.sh /scripts/
RUN chmod +x /scripts/backup_loop.sh /scripts/restaurar.sh

ENTRYPOINT ["/scripts/backup_loop.sh"]
