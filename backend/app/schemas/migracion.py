import datetime

from pydantic import BaseModel


class MigracionDisponibleOut(BaseModel):
    disponible: bool
    motivo: str | None = None


class ErrorValidacionMigracion(BaseModel):
    hoja: str
    fila: int
    campo: str | None = None
    mensaje: str


class ResumenMigracion(BaseModel):
    empleados: int
    contratos: int
    tramos_salario_adicionales: int
    dias_vacaciones_acumulados_totales: str
    isr_total_a_cargar: str
    meses_bruto_historico_cargados: int


class ResultadoValidacionMigracion(BaseModel):
    errores: list[ErrorValidacionMigracion]
    resumen: ResumenMigracion | None = None


class ResultadoMigracionOut(BaseModel):
    resumen: ResumenMigracion
    fecha_corte: datetime.date
