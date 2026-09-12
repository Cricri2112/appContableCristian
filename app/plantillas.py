"""Instancia única de templates Jinja2, compartida por todas las rutas.

Registra los filtros de formato (importes, fechas, etiquetas de enums)
para que los templates no tengan lógica de presentación propia.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.services import formato

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

templates.env.filters["fecha"] = formato.formato_fecha
templates.env.filters["fecha_larga"] = formato.fecha_larga
templates.env.filters["importe"] = formato.formato_importe
templates.env.filters["regimen"] = formato.regimen_legible
templates.env.filters["frecuencia"] = formato.frecuencia_legible


def _hoy():
    """Fecha actual en Montevideo, para la barra superior del cascarón."""
    from app.models.base import ahora_montevideo

    return ahora_montevideo().date()


templates.env.globals["hoy"] = _hoy
