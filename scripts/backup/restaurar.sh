#!/bin/sh
set -eu

# Auditoría de seguridad 2026-08-25 (hallazgo M6): un backup que nunca se
# probó a restaurar no es un backup, es una esperanza. Este script
# restaura un dump en una base de datos NUEVA Y DESCARTABLE -- nunca
# sobre la base real -- para poder verificar periódicamente que los
# backups generados por backup_loop.sh realmente sirven.
#
# Uso (desde el host, con el stack de producción levantado):
#   docker compose -f docker-compose.prod.yml exec backup \
#     /scripts/restaurar.sh nomina_20260826_030000.sql.gz nomina_prueba_restauracion
#
# Al terminar de revisar, borrá la base de prueba:
#   docker compose -f docker-compose.prod.yml exec db \
#     dropdb -U "$POSTGRES_USER" nomina_prueba_restauracion

ARCHIVO="${1:?Uso: restaurar.sh <archivo.sql.gz en /backups> <bd_destino>}"
BD_DESTINO="${2:?Uso: restaurar.sh <archivo.sql.gz en /backups> <bd_destino>}"
RUTA="/backups/$ARCHIVO"

if [ "$BD_DESTINO" = "${PGDATABASE:-}" ]; then
    echo "ERROR: bd_destino no puede ser la base de datos real ($PGDATABASE)." >&2
    exit 1
fi

if [ ! -f "$RUTA" ]; then
    echo "ERROR: no existe $RUTA" >&2
    exit 1
fi

echo "Creando base de datos de prueba: $BD_DESTINO"
createdb "$BD_DESTINO"

echo "Restaurando $RUTA en $BD_DESTINO..."
gunzip -c "$RUTA" | psql -d "$BD_DESTINO" --set ON_ERROR_STOP=1 -q

filas_empresas=$(psql -d "$BD_DESTINO" -t -A -c "SELECT count(*) FROM empresas;")
echo "Restauración OK. Empresas en la BD restaurada: $filas_empresas"
echo "Revisá lo que necesites y después borrá la BD de prueba con:"
echo "  docker compose -f docker-compose.prod.yml exec db dropdb -U \$POSTGRES_USER $BD_DESTINO"
