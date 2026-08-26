#!/bin/sh
set -eu

# Auditoría de seguridad 2026-08-25 (hallazgo M6): hasta esta fecha no
# existía ningún backup de la base de datos -- sin esto, un bug de
# migración, una corrupción o un ataque no tenían ningún camino de
# recuperación. Corre en el contenedor "backup" (ver docker-compose.prod.yml),
# que NUNCA comparte el volumen /backups con backend/frontend: un
# atacante que comprometa la app no puede alcanzar ni borrar los backups
# desde ahí.

RETENCION_DIAS="${BACKUP_RETENCION_DIAS:-14}"
INTERVALO_SEGUNDOS="${BACKUP_INTERVALO_SEGUNDOS:-86400}"
DESTINO=/backups

marca_de_tiempo() {
    date '+%Y-%m-%dT%H:%M:%S%z'
}

hacer_backup() {
    base="$DESTINO/nomina_$(date '+%Y%m%d_%H%M%S')"
    if pg_dump >"$base.sql" 2>"$base.err"; then
        gzip "$base.sql"
        rm -f "$base.err"
        echo "$(marca_de_tiempo) Backup OK: $base.sql.gz ($(du -h "$base.sql.gz" | cut -f1))"
    else
        echo "$(marca_de_tiempo) ERROR: pg_dump falló -- detalle en $base.err" >&2
        rm -f "$base.sql"
    fi
}

purgar_viejos() {
    echo "$(marca_de_tiempo) Purgando backups con más de ${RETENCION_DIAS} días en $DESTINO"
    find "$DESTINO" -maxdepth 1 \( -name 'nomina_*.sql.gz' -o -name 'nomina_*.err' \) \
        -mtime "+${RETENCION_DIAS}" -print -delete
}

while true; do
    hacer_backup
    purgar_viejos
    sleep "$INTERVALO_SEGUNDOS"
done
