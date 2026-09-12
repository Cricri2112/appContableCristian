"""Tabla `recordatorios` (Chat 2 + Chat 3 F10 + enmienda A1).

Enmienda A1: campos de referencia por tipo (`vencimiento_id`, `cliente_id`,
`periodo`, `umbral_dias`) para anti-duplicados y cierre automático.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import EstadoRecordatorio, TipoRecordatorio


class Recordatorio(Base, ConTimestamps):
    __tablename__ = "recordatorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Usado por tipo `tarea_pendiente`
    tarea_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tareas.id"), nullable=True
    )
    tipo: Mapped[TipoRecordatorio] = mapped_column(
        Enum(TipoRecordatorio), nullable=False
    )
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    fecha_programada: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # null = aún no enviado
    fecha_enviada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    estado: Mapped[EstadoRecordatorio] = mapped_column(
        Enum(EstadoRecordatorio), nullable=False
    )
    repetir_hasta_completar: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    intervalo_repeticion_horas: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # Chat 3, cambio 4: silenciado mientras silenciado_hasta >= hoy
    silenciado_hasta: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Enmienda A1: campos de referencia por tipo ---
    # Usado por `vencimiento_proximo`
    vencimiento_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vencimientos_calendario.id"), nullable=True
    )
    # Usados por `cobro_pendiente`
    cliente_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("clientes.id"), nullable=True
    )
    # Primer día del mes impago
    periodo: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Usado por `vencimiento_proximo` (5, 2 o 1)
    umbral_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)
