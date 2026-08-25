from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Valores de desarrollo -- nunca deben llegar a producción. Ver
# Settings._rechazar_secretos_de_desarrollo_en_produccion: la app se niega
# a arrancar con ENVIRONMENT=production si detecta alguno de estos.
_JWT_SECRET_KEY_DEV = "dev-secret-change-me"
_POSTGRES_APP_PASSWORD_DEV = "nomina_app_dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Conexión con la que corre la app en tiempo de ejecución: rol de bajo
    # privilegio, sin BYPASSRLS, para que las políticas RLS de Postgres se
    # apliquen de verdad (el rol dueño de las tablas / superusuario NUNCA
    # está sujeto a RLS, sin importar las políticas).
    database_url: str = f"postgresql+psycopg://nomina_app:{_POSTGRES_APP_PASSWORD_DEV}@db:5432/nomina"
    # Conexión de superusuario, solo para Alembic (DDL, creación de roles,
    # grants). La app nunca debe usar esta URL en tiempo de ejecución.
    database_url_admin: str = "postgresql+psycopg://nomina:nomina@db:5432/nomina"

    environment: str = "development"

    # Usados por la migración que aprovisiona el rol de aplicación.
    postgres_app_user: str = "nomina_app"
    postgres_app_password: str = _POSTGRES_APP_PASSWORD_DEV

    jwt_secret_key: str = _JWT_SECRET_KEY_DEV
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Orígenes permitidos para llamadas cross-origin del frontend (Nuxt
    # corre en un puerto distinto al backend incluso en desarrollo, así
    # que el navegador exige CORS -- ver app/main.py). Lista separada
    # por comas.
    cors_allowed_origins: str = "http://localhost:3000"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origen.strip() for origen in self.cors_allowed_origins.split(",") if origen.strip()]

    @model_validator(mode="after")
    def _rechazar_secretos_de_desarrollo_en_produccion(self) -> "Settings":
        # Auditoría de seguridad 2026-08-25 (hallazgo C1): si el .env de
        # producción queda incompleto (falta la env var, typo, deploy a
        # medias), Pydantic caía silenciosamente a estos defaults -- ambos
        # son públicos (están en este archivo). Falla fuerte en el arranque
        # en vez de servir tráfico con un secreto conocido.
        if self.environment == "production":
            if self.jwt_secret_key == _JWT_SECRET_KEY_DEV:
                raise ValueError(
                    "JWT_SECRET_KEY no está configurado: no se puede arrancar en "
                    "producción con el secreto de desarrollo por defecto."
                )
            if self.postgres_app_password == _POSTGRES_APP_PASSWORD_DEV:
                raise ValueError(
                    "POSTGRES_APP_PASSWORD no está configurado: no se puede arrancar "
                    "en producción con la contraseña de desarrollo por defecto."
                )
        return self


settings = Settings()
