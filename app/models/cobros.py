"""Tablas `cobros` y `descuentos` (Chat 2)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import FormaPago, TipoComprobante


class Cobro(Base, ConTimestamps):
    """Dinero efectivamente recibido."""

    __tablename__ = "cobros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Redundante con servicio_contratado, pero conveniente para filtrado.
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=False
    )
    # null = cobro no vinculado a un servicio específico
    servicio_contratado_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("servicios_contratados.id"), nullable=True
    )
    periodo_desde: Mapped[date | None] = mapped_column(Date, nullable=True)
    periodo_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_cobro: Mapped[date] = mapped_column(Date, nullable=False)
    importe: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    forma_pago: Mapped[FormaPago] = mapped_column(Enum(FormaPago), nullable=False)
    tipo_comprobante: Mapped[TipoComprobante] = mapped_column(
        Enum(TipoComprobante), nullable=False
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)


class Descuento(Base, ConTimestamps):
    """Descuentos como concepto propio; se restan al calcular el saldo."""

    __tablename__ = "descuentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=False
    )
    servicio_contratado_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("servicios_contratados.id"), nullable=True
    )
    fecha: Mapped[date] = mapped_column(Date, nullable=False)
    # Siempre positivo (se valida en servicios)
    importe: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)
