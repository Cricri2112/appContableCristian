"""Utilidades de fechas por mes, en hora de Montevideo.

Los períodos se representan con el primer día del mes (Chat 2):
mayo 2025 → date(2025, 5, 1).
"""

from calendar import monthrange
from datetime import date

from app.models.base import ahora_montevideo


def hoy() -> date:
    return ahora_montevideo().date()


def primer_dia_mes(fecha: date) -> date:
    return fecha.replace(day=1)


def ultimo_dia_mes(fecha: date) -> date:
    return fecha.replace(day=monthrange(fecha.year, fecha.month)[1])


def mes_siguiente(fecha: date) -> date:
    if fecha.month == 12:
        return date(fecha.year + 1, 1, 1)
    return date(fecha.year, fecha.month + 1, 1)


def mes_anterior(fecha: date) -> date:
    if fecha.month == 1:
        return date(fecha.year - 1, 12, 1)
    return date(fecha.year, fecha.month - 1, 1)


def dia_en_mes(anio: int, mes: int, dia: int) -> date:
    """Fecha del día pedido; si no existe en ese mes, el último día real.

    Regla de F8: un vencimiento del día 31 en abril se toma el 30.
    """
    return date(anio, mes, min(dia, monthrange(anio, mes)[1]))


def parsear_periodo(texto: str | None) -> date | None:
    """"2026-09" (input type=month) → date(2026, 9, 1). Inválido → None."""
    if not texto:
        return None
    try:
        anio, mes = texto.split("-")[:2]
        return date(int(anio), int(mes), 1)
    except ValueError:
        return None
