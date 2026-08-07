from typing import Literal

# Una boleta es un recibo de una sola entidad (pago/vacación/liquidación):
# PDF para imprimir/entregar, Excel como una fila para reimportar a
# contabilidad. CSV no aplica -- no es un documento tabular.
FormatoBoleta = Literal["pdf", "excel"]

# La exportación de planilla es una tabla (todos los empleados de un
# período): Excel/CSV, no PDF -- sería una tabla enorme, no un documento.
FormatoExportacion = Literal["excel", "csv"]
