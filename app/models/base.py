"""Base declarativa, zona horaria y columnas comunes a todas las tablas."""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Zona horaria de toda la lógica de fechas (requisito transversal 4, Chat 4).
ZONA_HORARIA = ZoneInfo("America/Montevideo")


def ahora_montevideo() -> datetime:
    """Fecha y hora actual en America/Montevideo, sin tzinfo.

    SQLite no guarda zona horaria, así que almacenamos el datetime "naive"
    pero siempre calculado en hora de Montevideo.
    """
    return datetime.now(ZONA_HORARIA).replace(tzinfo=None)


class Base(DeclarativeBase):
    """Base declarativa de todos los modelos."""


class ConTimestamps:
    """Columnas created_at / updated_at automáticas.

    Enmienda A3: TODAS las tablas (incluida `tareas`) llevan estos campos.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=ahora_montevideo
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=ahora_montevideo, onupdate=ahora_montevideo
    )
