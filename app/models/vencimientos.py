"""Tabla `vencimientos_calendario` — referencia sin FKs salientes (Chat 2)."""

from sqlalchemy import Boolean, Enum, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import Organismo, RegimenAplicable


class VencimientoCalendario(Base, ConTimestamps):
    __tablename__ = "vencimientos_calendario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    regimen: Mapped[RegimenAplicable] = mapped_column(
        Enum(RegimenAplicable), nullable=False
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    organismo: Mapped[Organismo] = mapped_column(Enum(Organismo), nullable=False)
    # null = aplica todos los meses
    mes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Día del mes (1-31); si no existe en un mes, se muestra el último día real
    dia_vencimiento: Mapped[int] = mapped_column(Integer, nullable=False)
    # null = recurrente anualmente
    anio: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
