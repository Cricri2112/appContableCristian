"""Schemas Pydantic de autenticación."""

from pydantic import BaseModel


class FormularioLogin(BaseModel):
    """Datos del formulario de login. La lógica vive en el servicio."""

    usuario: str
    password: str
