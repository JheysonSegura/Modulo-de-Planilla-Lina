from slowapi import Limiter
from slowapi.util import get_remote_address

# Limiter compartido por toda la app -- ver main.py (exception handler +
# middleware) y routers/auth.py (límites por endpoint). Se resetea entre
# tests en tests/conftest.py::_reset_rate_limiter, porque todos los tests
# comparten la misma IP falsa del TestClient y contaminarían la ventana
# de conteo de un test al siguiente si no se reiniciara.
limiter = Limiter(key_func=get_remote_address)
