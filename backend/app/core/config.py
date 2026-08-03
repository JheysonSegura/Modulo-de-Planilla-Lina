from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Conexión con la que corre la app en tiempo de ejecución: rol de bajo
    # privilegio, sin BYPASSRLS, para que las políticas RLS de Postgres se
    # apliquen de verdad (el rol dueño de las tablas / superusuario NUNCA
    # está sujeto a RLS, sin importar las políticas).
    database_url: str = "postgresql+psycopg://nomina_app:nomina_app_dev@db:5432/nomina"
    # Conexión de superusuario, solo para Alembic (DDL, creación de roles,
    # grants). La app nunca debe usar esta URL en tiempo de ejecución.
    database_url_admin: str = "postgresql+psycopg://nomina:nomina@db:5432/nomina"

    environment: str = "development"

    # Usados por la migración que aprovisiona el rol de aplicación.
    postgres_app_user: str = "nomina_app"
    postgres_app_password: str = "nomina_app_dev"

    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7


settings = Settings()
