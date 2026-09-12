"""Tablas de sistema: `auditoria`, `scheduler_ejecuciones`, `usuario_login`.

- `auditoria` (Chat 4): registro automático append-only de toda creación,
  edición y eliminación, más intentos fallidos de login (enmienda A2).
- `scheduler_ejecuciones` (Chat 4): la escribe y lee solo el scheduler (E5+).
- `usuario_login` (Chat 5): usuario único de la app.
"""

from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ConTimestamps
from app.models.enums import AccionAuditoria, ProcesoScheduler


class Auditoria(Base, ConTimestamps):
    """Append-only: nunca se edita ni borra desde la app. Sin UI en el MVP."""

    __tablename__ = "auditoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    tabla: Mapped[str] = mapped_column(Text, nullable=False)
    registro_id: Mapped[int] = mapped_column(Integer, nullable=False)
    accion: Mapped[AccionAuditoria] = mapped_column(
        Enum(AccionAuditoria), nullable=False
    )
    # JSON como texto; null en creación
    datos_antes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON como texto; null en eliminación
    datos_despues: Mapped[str | None] = mapped_column(Text, nullable=True)


class SchedulerEjecucion(Base, ConTimestamps):
    __tablename__ = "scheduler_ejecuciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proceso: Mapped[ProcesoScheduler] = mapped_column(
        Enum(ProcesoScheduler), nullable=False
    )
    fecha_ejecucion: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # "ok" o detalle del error
    resultado: Mapped[str] = mapped_column(Text, nullable=False)


class UsuarioLogin(Base, ConTimestamps):
    """Usuario único de la app (Chat 5). Alta por script CLI, sin registro web."""

    __tablename__ = "usuario_login"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    usuario: Mapped[str] = mapped_column(Text, nullable=False)
    # Hash bcrypt (irreversible), NUNCA la contraseña en claro
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    intentos_fallidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
