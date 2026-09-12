"""Rutas de Configuración → Servicios (F3).

Los endpoints solo llaman servicios y devuelven HTML.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.plantillas import templates
from app.services import catalogo
from app.services.errores import ErrorValidacion

router = APIRouter(prefix="/configuracion/servicios")


def _contexto_listado(db: Session) -> dict:
    return {"seccion": "configuracion", "filas": catalogo.listar_servicios(db)}


@router.get("", response_class=HTMLResponse)
def listado(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request, "configuracion_servicios.html", _contexto_listado(db)
    )


@router.get("/nuevo", response_class=HTMLResponse)
def form_crear(request: Request, db: Session = Depends(get_db)):
    contexto = _contexto_listado(db) | {
        "servicio": None, "valores": {}, "errores": {},
    }
    return templates.TemplateResponse(request, "servicio_form.html", contexto)


@router.post("/nuevo")
def crear(
    request: Request,
    nombre: str = Form(""),
    frecuencia: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        catalogo.crear_servicio(db, nombre, frecuencia)
    except ErrorValidacion as error:
        contexto = _contexto_listado(db) | {
            "servicio": None,
            "valores": {"nombre": nombre, "frecuencia": frecuencia},
            "errores": error.errores,
        }
        return templates.TemplateResponse(
            request, "servicio_form.html", contexto, status_code=422
        )
    return RedirectResponse("/configuracion/servicios", status_code=303)


@router.get("/{servicio_id}/editar", response_class=HTMLResponse)
def form_editar(request: Request, servicio_id: int, db: Session = Depends(get_db)):
    servicio = catalogo.obtener_servicio(db, servicio_id)
    contexto = _contexto_listado(db) | {
        "servicio": servicio,
        "valores": {
            "nombre": servicio.nombre,
            "frecuencia": servicio.frecuencia.value,
        },
        "errores": {},
        "frecuencia_bloqueada": catalogo.tiene_contratos_activos(db, servicio_id),
    }
    return templates.TemplateResponse(request, "servicio_form.html", contexto)


@router.post("/{servicio_id}/editar")
def editar(
    request: Request,
    servicio_id: int,
    nombre: str = Form(""),
    frecuencia: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        catalogo.editar_servicio(db, servicio_id, nombre, frecuencia)
    except ErrorValidacion as error:
        servicio = catalogo.obtener_servicio(db, servicio_id)
        contexto = _contexto_listado(db) | {
            "servicio": servicio,
            "valores": {"nombre": nombre, "frecuencia": frecuencia},
            "errores": error.errores,
            "frecuencia_bloqueada": catalogo.tiene_contratos_activos(db, servicio_id),
        }
        return templates.TemplateResponse(
            request, "servicio_form.html", contexto, status_code=422
        )
    return RedirectResponse("/configuracion/servicios", status_code=303)


@router.post("/{servicio_id}/activo")
def cambiar_activo(servicio_id: int, db: Session = Depends(get_db)):
    """Desactivar/reactivar: un clic, sin diálogo de confirmación."""
    catalogo.cambiar_activo(db, servicio_id)
    return RedirectResponse("/configuracion/servicios", status_code=303)
