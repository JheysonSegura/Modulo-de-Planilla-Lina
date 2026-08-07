from typing import Literal

# Un recibo es el documento de una sola entidad (pago/vacación/liquidación):
# PDF para imprimir/entregar, Excel como una fila para reimportar a
# contabilidad. CSV no aplica -- no es un documento tabular.
FormatoRecibo = Literal["pdf", "excel"]

# Exportación de planilla completa (todos los empleados de un período):
# Excel/CSV para contabilidad, PDF como reporte consolidado para
# imprimir/archivar (Fase 16, extensión 2026-08-07).
FormatoExportacion = Literal["excel", "csv", "pdf"]

# Reporte de auditoría: tabular (Excel/CSV) para análisis, sin PDF -- un
# log de auditoría puede crecer indefinidamente, no tiene sentido como
# documento de una sola página.
FormatoAuditoria = Literal["excel", "csv"]
