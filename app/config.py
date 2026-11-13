"""Configuración de la aplicación.

Todos los secretos viven en variables de entorno (o en el archivo `.env`
local, que nunca se sube al repo). Requisito transversal 2 del Chat 4.
"""

import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Valores de configuración leídos del entorno / `.env`."""

    # Secreto para firmar la cookie de sesión. Obligatorio, sin default.
    secret_key: str

    # Base SQLite en archivo único (Chat 4, decisión 2).
    database_url: str = "sqlite:///./estudio.db"

    # Clave Fernet del vault de credenciales (Chat 4, decisión 6).
    # Es opcional ACÁ para que Alembic y los scripts funcionen sin ella;
    # la app web se niega a arrancar si falta (ver app/main.py).
    fernet_key: str | None = None

    # Procesos programados (APScheduler). Se apaga en los tests.
    scheduler_activo: bool = True

    # Email transaccional por API (Chat 4, decisión 7; Etapa 6: Brevo).
    # Sin clave o sin remitente, el email diario no se envía y queda
    # registrado en scheduler_ejecuciones (el ciclo diario sigue igual).
    brevo_api_key: str | None = None
    email_remitente: str | None = None

    # Dirección de la app, para el link al pie del email.
    app_url: str = "http://localhost:8000"

    # Carpeta de respaldos diarios de la base (Chat 4, decisión 4). En
    # desarrollo es local; el destino externo se configura en la Etapa 7.
    respaldos_dir: str = "./respaldos"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


def cargar_configuracion() -> Settings:
    """Carga la configuración y falla con mensaje claro si falta un secreto."""
    try:
        return Settings()
    except Exception:
        print(
            "ERROR: falta configurar SECRET_KEY.\n"
            "Copiá .env.example como .env y completá SECRET_KEY "
            '(generarla con: python -c "import secrets; print(secrets.token_urlsafe(32))").',
            file=sys.stderr,
        )
        raise


settings = cargar_configuracion()
