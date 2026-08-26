import logging

# Auditoría de seguridad 2026-08-25 (hallazgo M5): antes no había ningún
# logging.getLogger/print en todo el backend -- cero registro de intentos
# de login fallidos o resets de password más allá del access log HTTP
# default de uvicorn (que no identifica el email/usuario involucrado).
LOGGER_SEGURIDAD = "nomina.seguridad"


def configurar_logging() -> None:
    formato = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    # Root a WARNING con su propio handler: un basicConfig(level=INFO) sin
    # matices resultó destapar el logging interno de fontTools (invocado
    # por WeasyPrint al generar cada recibo PDF, que se auto-configura a
    # DEBUG para medir tiempos de subsetting) -- antes esas líneas no
    # tenían ningún handler que las sacara a algún lado, así que quedaban
    # calladas; en cuanto el root tuvo un StreamHandler, inundaron el log.
    handler_raiz = logging.StreamHandler()
    handler_raiz.setFormatter(formato)
    handler_raiz.setLevel(logging.WARNING)
    logging.basicConfig(level=logging.WARNING, handlers=[handler_raiz])

    # El logger de seguridad tiene su propio handler a INFO y no propaga
    # al root -- sus eventos (login fallido, reset de password) siempre se
    # ven, sin depender del tope de WARNING de arriba ni de qué nivel le
    # imponga una librería de terceros a sus propios loggers en runtime.
    logger_seguridad = logging.getLogger(LOGGER_SEGURIDAD)
    handler_seguridad = logging.StreamHandler()
    handler_seguridad.setFormatter(formato)
    logger_seguridad.addHandler(handler_seguridad)
    logger_seguridad.setLevel(logging.INFO)
    logger_seguridad.propagate = False
