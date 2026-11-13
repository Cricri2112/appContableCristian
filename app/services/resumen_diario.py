"""Email resumen diario de recordatorios (F10, entrega 2).

Un único email por día, solo si hay al menos un recordatorio activo no
silenciado, agrupado como el panel. Si falla, se lanza ErrorEmail y quien
llama lo registra en scheduler_ejecuciones sin cortar el ciclo.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.config import settings
from app.models.base import ahora_montevideo
from app.services import ajustes, email, formato, recordatorios


def _renderizar(grupos, hoy: date, cantidad: int) -> str:
    from app.plantillas import templates

    return templates.env.get_template("emails/resumen_diario.html").render(
        grupos=grupos,
        fecha=formato.fecha_larga(hoy),
        cantidad=cantidad,
        app_url=settings.app_url.rstrip("/"),
    )


def enviar_resumen(db: Session, hoy: date) -> str:
    """Envía el resumen si corresponde. Devuelve un texto para el registro
    del ciclo; lanza email.ErrorEmail si el envío falla."""
    pendientes = recordatorios.para_email(db, hoy)
    if not pendientes:
        return "email: sin recordatorios activos, no se envía"

    cantidad = len(pendientes)
    asunto = (
        "Estudio: 1 recordatorio activo" if cantidad == 1
        else f"Estudio: {cantidad} recordatorios activos"
    )
    html = _renderizar(recordatorios.agrupar_para_email(pendientes), hoy, cantidad)
    email.enviar_email(ajustes.email_destino(db), asunto, html)

    recordatorios.marcar_enviados(pendientes, ahora_montevideo())
    db.commit()
    return f"email: enviado con {cantidad} recordatorio{'s' if cantidad != 1 else ''}"
