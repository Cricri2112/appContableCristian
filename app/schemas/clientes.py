"""Schemas Pydantic de F1: convierten los datos crudos del formulario.

Los campos opcionales vacíos ("") se convierten a None; las fechas llegan
como aaaa-mm-dd del input type=date. Las validaciones de NEGOCIO (unicidad,
RUT de 12 dígitos, fechas no futuras) viven en la capa de servicios.
"""

from datetime import date

from pydantic import BaseModel, field_validator


class FormularioCliente(BaseModel):
    nombre: str = ""
    regimen: str = ""
    rut: str | None = None
    ci: str | None = None
    fecha_nacimiento: date | None = None
    email: str | None = None
    telefono: str | None = None
    fecha_inicio: date | None = None
    notas: str | None = None

    @field_validator(
        "rut", "ci", "email", "telefono", "notas", mode="before"
    )
    @classmethod
    def vacio_a_none(cls, valor):
        if isinstance(valor, str):
            valor = valor.strip()
        return valor or None

    @field_validator("fecha_nacimiento", "fecha_inicio", mode="before")
    @classmethod
    def fecha_vacia_a_none(cls, valor):
        return valor or None

    @field_validator("nombre", "regimen", mode="before")
    @classmethod
    def recortar(cls, valor):
        return valor.strip() if isinstance(valor, str) else valor
