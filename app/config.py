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
