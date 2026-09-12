"""Tablas `clientes` y `clientes_regimen_historial` (Chat 2 + Chat 3)."""

from datetime import date

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import Regimen


class Cliente(Base, ConTimestamps):
    """Todos los clientes, mensuales y eventuales, en una sola tabla."""

    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    # `regimen` siempre refleja el régimen vigente (redundante con el
    # historial, pero conveniente para filtrado rápido — F1).
    regimen: Mapped[Regimen] = mapped_column(Enum(Regimen), nullable=False)
    rut: Mapped[str | None] = mapped_column(Text, nullable=True)
    ci: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_nacimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)


class ClienteRegimenHistorial(Base, ConTimestamps):
    """Historial de regímenes del cliente (Chat 3, cambio 1).

    Regla: un solo registro con fecha_hasta = null por cliente (se valida
    en la capa de servicios, no en la base).
    """

    __tablename__ = "clientes_regimen_historial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=False
    )
    regimen: Mapped[Regimen] = mapped_column(Enum(Regimen), nullable=False)
    fecha_desde: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
