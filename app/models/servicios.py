"""Tablas `servicios`, `servicios_contratados` y `honorarios_historial`."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import FrecuenciaServicio


class Servicio(Base, ConTimestamps):
    """Catálogo de lo que se vende. Pocos registros, estables."""

    __tablename__ = "servicios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    frecuencia: Mapped[FrecuenciaServicio] = mapped_column(
        Enum(FrecuenciaServicio), nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ServicioContratado(Base, ConTimestamps):
    """Vincula cliente con servicio. Un cliente puede tener varios."""

    __tablename__ = "servicios_contratados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=False
    )
    servicio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servicios.id"), nullable=False
    )
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    # null = vigente
    fecha_fin: Mapped[date | None] = mapped_column(Date, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HonorarioHistorial(Base, ConTimestamps):
    """Log append-only de cambios de honorario por servicio contratado.

    Regla: un solo registro con fecha_hasta = null por servicio_contratado_id
    (se valida en la capa de servicios).
    """

    __tablename__ = "honorarios_historial"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    servicio_contratado_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servicios_contratados.id"), nullable=False
    )
    honorario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fecha_desde: Mapped[date] = mapped_column(Date, nullable=False)
    # null = honorario vigente
    fecha_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
