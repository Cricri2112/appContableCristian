"""Tablas `tarea_templates` y `tareas` (Chat 2 + Chat 3, F7).

Enmienda A3: `tareas` también lleva created_at/updated_at automáticos;
`fecha_creacion` y `fecha_completada` se mantienen como campos de negocio.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import EstadoTarea, RegimenAplicable


class TareaTemplate(Base, ConTimestamps):
    """Plantillas de tareas por combinación servicio + régimen."""

    __tablename__ = "tarea_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    servicio_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servicios.id"), nullable=False
    )
    # Enum de regímenes más el valor `todos`
    regimen: Mapped[RegimenAplicable] = mapped_column(
        Enum(RegimenAplicable), nullable=False
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    # Chat 3, cambio 3: obligatorio si el servicio es anual (mes 1-12),
    # null si es mensual o único. Se valida en la capa de servicios.
    mes_generacion: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Tarea(Base, ConTimestamps):
    """Instancias concretas generadas por cliente y período."""

    __tablename__ = "tareas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    servicio_contratado_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("servicios_contratados.id"), nullable=False
    )
    # null = tarea ad-hoc
    template_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tarea_templates.id"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    # Primer día del mes/año que aplica
    periodo: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[EstadoTarea] = mapped_column(Enum(EstadoTarea), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fecha_completada: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    requiere_info_cliente: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
