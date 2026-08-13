import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core import deps as deps_module
from app.core.config import settings
from app.core.security import hash_password
from app.main import app
from app.models import Empleado, Empresa, Rol, SalarioMinimoVigente, Usuario, UsuarioEmpresa

TEST_DB_NAME = "nomina_test"
BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")


def _url_with_db(base_url: str, dbname: str):
    """Devuelve un objeto URL (no un str: str(URL) oculta el password
    desde SQLAlchemy 1.4+ y rompería la conexión real)."""
    return make_url(base_url).set(database=dbname)


@pytest.fixture(scope="session", autouse=True)
def _preparar_base_de_datos():
    """Recrea nomina_test desde cero y corre 'alembic upgrade head' contra
    ella, para probar el pipeline real de migraciones (incluido el rol de
    aplicación y las políticas RLS), no una BD armada a mano."""
    root_url = _url_with_db(settings.database_url_admin, "postgres")
    root_engine = create_engine(root_url, isolation_level="AUTOCOMMIT")
    with root_engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    root_engine.dispose()

    admin_test_url = _url_with_db(settings.database_url_admin, TEST_DB_NAME)
    alembic_cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "alembic"))
    alembic_cfg.set_main_option(
        "sqlalchemy.url", admin_test_url.render_as_string(hide_password=False)
    )
    command.upgrade(alembic_cfg, "head")

    yield


@pytest.fixture(scope="session")
def engine():
    app_test_url = _url_with_db(settings.database_url, TEST_DB_NAME)
    eng = create_engine(app_test_url)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def SessionTest(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db(SessionTest):
    session = SessionTest()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(SessionTest):
    def override_get_db():
        session = SessionTest()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[deps_module.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --- Helpers de datos de prueba (no son fixtures: se llaman explícitamente
# desde cada test para controlar exactamente qué empresas/usuarios arma) ---


def crear_empresa(db, sufijo: str) -> Empresa:
    empresa = Empresa(razon_social=f"Empresa {sufijo}", ruc=f"RUC-{sufijo}", moneda="USD")
    db.add(empresa)
    db.commit()
    db.refresh(empresa)
    return empresa


def crear_usuario(
    db,
    email: str,
    password: str = "Secreta123!",
    es_superadmin: bool = False,
    puede_crear_empresas: bool = False,
) -> Usuario:
    usuario = Usuario(
        email=email,
        password_hash=hash_password(password),
        nombre_completo="Usuario de prueba",
        es_superadmin=es_superadmin,
        puede_crear_empresas=puede_crear_empresas,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def vincular(db, usuario: Usuario, empresa: Empresa, rol_nombre: str = "admin") -> UsuarioEmpresa:
    rol = db.scalar(select(Rol).where(Rol.nombre == rol_nombre))
    membresia = UsuarioEmpresa(usuario_id=usuario.id, empresa_id=empresa.id, rol_id=rol.id)
    db.add(membresia)
    db.commit()
    return membresia


def crear_empleado(db, empresa: Empresa, nombre: str, identificacion: str) -> Empleado:
    # empleados tiene RLS con FORCE: incluso este insert directo necesita
    # app.empresa_actual fijado, o la política lo rechaza.
    db.execute(
        text("SELECT set_config('app.empresa_actual', :eid, false)"),
        {"eid": str(empresa.id)},
    )
    empleado = Empleado(
        empresa_id=empresa.id, nombre_completo=nombre, identificacion=identificacion
    )
    db.add(empleado)
    db.commit()
    db.refresh(empleado)
    return empleado


def crear_salario_minimo(
    db,
    fecha_inicio,
    monto_mensual=None,
    region: str = "Nacional",
    fecha_fin=None,
    actividad: str | None = None,
    limpiar: bool = True,
    monto_hora=None,
    tamano_empresa: str | None = None,
) -> SalarioMinimoVigente:
    # salario_minimo_vigente es dato global (no por empresa): por defecto
    # se limpia antes de sembrar para que un test no choque con rangos de
    # fecha que dejó otro test en la misma BD de test compartida entre
    # casos. limpiar=False permite sembrar varias filas a propósito (para
    # probar la resolución multi-región/tamaño de empresa).
    if limpiar:
        db.query(SalarioMinimoVigente).delete()
    fila = SalarioMinimoVigente(
        region=region,
        actividad=actividad,
        tamano_empresa=tamano_empresa,
        monto_mensual=monto_mensual,
        monto_hora=monto_hora,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        decreto_ref="Decreto Ejecutivo N.13 (dato de prueba)",
    )
    db.add(fila)
    db.commit()
    db.refresh(fila)
    return fila


def login_y_seleccionar(client, usuario: Usuario, empresa: Empresa, password: str = "Secreta123!") -> dict:
    """Hace login y selecciona `empresa` como activa; devuelve los headers
    con el access_token ya listo para usar contra endpoints con RLS."""
    resp = client.post("/auth/login", json={"email": usuario.email, "password": password})
    assert resp.status_code == 200, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}

    resp = client.post(
        "/auth/seleccionar-empresa", json={"empresa_id": str(empresa.id)}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
