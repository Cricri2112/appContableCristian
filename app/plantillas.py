"""Instancia única de templates Jinja2, compartida por todas las rutas.

Registra los filtros de formato (importes, fechas, etiquetas de enums)
para que los templates no tengan lógica de presentación propia.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.services import formato


def _contexto_global(request) -> dict:
    """Disponible en todos los templates: progreso de tareas del período
    en curso para el menú lateral (hallazgo H-02). Se calcula solo si el
    template lo usa y si la ruta tiene sesión de base."""

    def progreso_tareas():
        db = getattr(request.state, "db", None)
        if db is None:
            return None
        from app.services import fechas, tareas

        return tareas.progreso_periodo(db, fechas.primer_dia_mes(fechas.hoy()))

    return {"progreso_tareas": progreso_tareas}


templates = Jinja2Templates(
    directory=Path(__file__).parent / "templates",
    context_processors=[_contexto_global],
)

templates.env.filters["fecha"] = formato.formato_fecha
templates.env.filters["fecha_larga"] = formato.fecha_larga
templates.env.filters["importe"] = formato.formato_importe
templates.env.filters["regimen"] = formato.regimen_legible
templates.env.filters["frecuencia"] = formato.frecuencia_legible
templates.env.filters["mes_corto"] = formato.mes_corto
templates.env.filters["mes_abrev"] = formato.mes_abreviado
templates.env.filters["periodo"] = formato.formato_periodo
templates.env.filters["mes_largo"] = formato.mes_largo
templates.env.filters["nombre_mes"] = formato.nombre_mes


def _hoy():
    """Fecha actual en Montevideo, para la barra superior del cascarón."""
    from app.models.base import ahora_montevideo

    return ahora_montevideo().date()


templates.env.globals["hoy"] = _hoy
