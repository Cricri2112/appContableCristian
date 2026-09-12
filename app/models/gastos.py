"""Tabla `gastos_ingresos_propios` — P&L del estudio, sin FKs (Chat 2)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import CategoriaMovimientoPropio, TipoMovimientoPropio


class GastoIngresoPropio(Base, ConTimestamps):
    __tablename__ = "gastos_ingresos_propios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    tipo: Mapped[TipoMovimientoPropio] = mapped_column(
        Enum(TipoMovimientoPropio), nullable=False
    )
    concepto: Mapped[str] = mapped_column(Text, nullable=False)
    importe: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    categoria: Mapped[CategoriaMovimientoPropio] = mapped_column(
        Enum(CategoriaMovimientoPropio), nullable=False
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
