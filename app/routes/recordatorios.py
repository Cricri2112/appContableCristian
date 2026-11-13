"""Rutas de F10: panel de recordatorios (campanita) y Configuración →
Notificaciones (email de destino + estado de los procesos, H-10)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.plantillas import templates
from app.services import ajustes, email, recordatorios, scheduler
from app.services.errores import ErrorValidacion

router = APIRouter()


def _panel(request: Request, db: Session, error: str | None = None):
    return templates.TemplateResponse(request, "_panel_recordatorios.html", {
        "items": recordatorios.panel(db),
        "mensaje_no_silenciable": recordatorios.MENSAJE_NO_SILENCIABLE,
        "error": error,
    })


@router.get("/recordatorios/panel", response_class=HTMLResponse)
def panel(request: Request, db: Session = Depends(get_db)):
    """Contenido del panel; se carga por HTMX al tocar la campanita."""
    return _panel(request, db)


@router.post("/recordatorios/{recordatorio_id}/silenciar", response_class=HTMLResponse)
def silenciar(
    request: Request,
    recordatorio_id: int,
    dias: int = Form(...),
    db: Session = Depends(get_db),
):
    error = None
    try:
        recordatorios.silenciar(db, recordatorio_id, dias)
    except ErrorValidacion as e:
        error = " ".join(e.errores.values())
    return _panel(request, db, error)


# ---------- Configuración → Notificaciones (vista 23) ----------

def _contexto_notificaciones(db: Session) -> dict:
    return {
        "seccion": "configuracion",
        "email_destino": ajustes.email_destino(db) or "",
        "email_configurado": email.configurado(),
        "ultimo_diario": scheduler.ultima_ejecucion(db, "diario"),
        "ultimo_mensual": scheduler.ultima_ejecucion(db, "mensual"),
        "errores": {},
        "guardado": False,
    }


@router.get("/configuracion/notificaciones", response_class=HTMLResponse)
def notificaciones(request: Request, guardado: int = 0, db: Session = Depends(get_db)):
    contexto = _contexto_notificaciones(db) | {"guardado": bool(guardado)}
    return templates.TemplateResponse(request, "configuracion_notificaciones.html", contexto)


@router.post("/configuracion/notificaciones")
def guardar_notificaciones(
    request: Request,
    email_destino: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        ajustes.guardar_email_destino(db, email_destino)
    except ErrorValidacion as error:
        contexto = _contexto_notificaciones(db) | {
            "email_destino": email_destino,
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "configuracion_notificaciones.html", contexto, status_code=422
        )
    return RedirectResponse("/configuracion/notificaciones?guardado=1", status_code=303)
