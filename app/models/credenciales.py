"""Tabla `credenciales` — vault cifrado (Chat 2 + Chat 3, F2).

Los campos `usuario`, `password` y `notas` se almacenan CIFRADOS.
El cifrado Fernet se implementa en la Etapa 4; el esquema ya lo contempla.
En `auditoria` estos campos se registran siempre como "[cifrado]".
"""

from datetime import date

from sqlalchemy import Date, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import TipoCredencial


class Credencial(Base, ConTimestamps):
    __tablename__ = "credenciales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=False
    )
    tipo: Mapped[TipoCredencial] = mapped_column(Enum(TipoCredencial), nullable=False)
    usuario: Mapped[str | None] = mapped_column(Text, nullable=True)   # cifrado
    password: Mapped[str | None] = mapped_column(Text, nullable=True)  # cifrado
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)     # cifrado
    ultima_actualizacion: Mapped[date] = mapped_column(Date, nullable=False)
